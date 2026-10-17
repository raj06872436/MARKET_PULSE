import { type FormEvent, useCallback, useEffect, useState } from "react";

import { api } from "../api/client";
import type { Alert, AlertEvent, AlertMetric, Watchlist } from "../types/api";

const METRICS: { key: AlertMetric; label: string; unit: string; hint: string; fallback: number }[] = [
  { key: "daily_mentions", label: "Daily mentions", unit: "posts", hint: "on the latest collected day", fallback: 50 },
  { key: "weekly_change", label: "Weekly change in mentions", unit: "%", hint: "last 7 collected days against the 7 before", fallback: 50 },
  { key: "negative_share", label: "Negative share", unit: "%", hint: "of scored posts over 7 days, needs at least 10", fallback: 40 },
  { key: "trend_score", label: "Trend score", unit: "", hint: "0 to 100, 50 means no change", fallback: 70 },
];
const COOLDOWNS = [
  { minutes: 360, label: "6 hours" },
  { minutes: 1440, label: "1 day" },
  { minutes: 10080, label: "1 week" },
];

function describe(alert: Alert): string {
  const m = METRICS.find((x) => x.key === alert.rule.metric);
  const unit = m?.unit === "%" ? "%" : m?.unit ? ` ${m.unit}` : "";
  return `${m?.label ?? alert.rule.metric} at or above ${alert.rule.threshold}${unit}`;
}

/** Threshold alerts for one watchlist. Alerts show here only; nothing is emailed or posted anywhere. */
export function AlertsPanel({ watchlist }: { watchlist: Watchlist }) {
  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [events, setEvents] = useState<AlertEvent[]>([]);
  const [entityId, setEntityId] = useState(watchlist.entities[0]?.id ?? "");
  const [metric, setMetric] = useState<AlertMetric>("daily_mentions");
  const [threshold, setThreshold] = useState("50");
  const [cooldown, setCooldown] = useState(1440);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [a, e] = await Promise.all([api.alerts(watchlist.id), api.alertEvents(watchlist.id, 5)]);
    setAlerts(a);
    setEvents(e);
  }, [watchlist.id]);

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Could not load alerts"));
  }, [load]);

  useEffect(() => {
    if (!watchlist.entities.some((e) => e.id === entityId)) setEntityId(watchlist.entities[0]?.id ?? "");
  }, [watchlist.entities, entityId]);

  async function act(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      await load();
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      return false;
    }
  }

  async function create(event: FormEvent) {
    event.preventDefault();
    const value = Number(threshold);
    if (!entityId || threshold === "" || Number.isNaN(value)) return;
    await act(() => api.createAlert(entityId, { metric, threshold: value }, cooldown));
  }

  const chosen = METRICS.find((m) => m.key === metric)!;
  const id = (name: string) => `alert-${name}-${watchlist.id}`;

  return (
    <details className="mt-4 border-t border-slate-100 pt-3">
      <summary className="cursor-pointer text-sm font-medium text-slate-700">
        Alerts {alerts && alerts.length > 0 && <span className="font-normal text-slate-500">({alerts.length})</span>}
        {events.length > 0 && <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-normal text-amber-800">
          last fired {events[0].data_date}</span>}
      </summary>
      <p className="mt-2 text-xs text-slate-500">
        Checked after every import or sync, on each term's latest collected day. Days nobody collected never count as zero.
        Alerts appear here only.
      </p>
      {error && <p className="mt-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      {alerts && alerts.length > 0 && (
        <ul className="mt-3 divide-y divide-slate-100 text-sm">
          {alerts.map((a) => (
            <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span className={a.active ? "text-slate-800" : "text-slate-500"}>
                <span className="font-medium">{a.term}</span>: {describe(a)}
                <span className="text-xs text-slate-500"> · at most once every {COOLDOWNS.find((c) => c.minutes === a.cooldown_minutes)?.label ?? `${a.cooldown_minutes} minutes`}</span>
              </span>
              <span className="flex gap-2">
                <button onClick={() => act(() => api.updateAlert(a.id, { active: !a.active }))}
                  className="rounded-md border border-slate-300 px-2 py-0.5 text-xs hover:bg-slate-50">{a.active ? "Pause" : "Resume"}</button>
                <button onClick={() => act(() => api.deleteAlert(a.id))} aria-label={`Delete alert for ${a.term}`}
                  className="rounded-md border border-red-200 px-2 py-0.5 text-xs text-red-700 hover:bg-red-50">Delete</button>
              </span>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={create} className="mt-3 grid gap-2 sm:grid-cols-[1fr_1.4fr_6rem_7rem_auto] sm:items-end">
        <div className="flex flex-col gap-1">
          <label htmlFor={id("term")} className="text-xs text-slate-500">Term</label>
          <select id={id("term")} value={entityId} onChange={(e) => setEntityId(e.target.value)}
            className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm">
            {watchlist.entities.map((e) => <option key={e.id} value={e.id}>{e.term}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={id("metric")} className="text-xs text-slate-500">When</label>
          <select id={id("metric")} value={metric} onChange={(e) => {
            const next = e.target.value as AlertMetric;
            setMetric(next);
            setThreshold(String(METRICS.find((m) => m.key === next)!.fallback));
          }} className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm">
            {METRICS.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={id("threshold")} className="text-xs text-slate-500">Reaches{chosen.unit && ` (${chosen.unit})`}</label>
          <input id={id("threshold")} type="number" min={0} max={metric === "trend_score" ? 100 : 100000} step="any" required
            value={threshold} onChange={(e) => setThreshold(e.target.value)}
            className="rounded-md border border-slate-300 px-2 py-1.5 text-sm tabular-nums" />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={id("cooldown")} className="text-xs text-slate-500">At most every</label>
          <select id={id("cooldown")} value={cooldown} onChange={(e) => setCooldown(Number(e.target.value))}
            className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm">
            {COOLDOWNS.map((c) => <option key={c.minutes} value={c.minutes}>{c.label}</option>)}
          </select>
        </div>
        <button className="rounded-md bg-slate-800 px-3 py-1.5 text-sm text-white hover:bg-slate-900">Add alert</button>
      </form>
      <p className="mt-1 text-xs text-slate-500">{chosen.label}: {chosen.hint}.</p>

      {events.length > 0 && (
        <div className="mt-3">
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-500">Recent alerts</h3>
          <ul className="mt-1 space-y-1 text-sm text-slate-700">
            {events.map((e) => <li key={e.id}>{e.message}</li>)}
          </ul>
        </div>
      )}
    </details>
  );
}
