import { type ReactNode, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { ForecastChart, ForecastLegend } from "../charts/ForecastChart";
import { pct, shortDate } from "../charts/format";
import { seriesColor } from "../charts/palette";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { useFilters } from "../hooks/useFilters";
import type { Forecast, Watchlist } from "../types/api";

const CHECK_LABELS: Record<string, string> = {
  history: "Enough history",
  coverage: "Recent days collected",
  sparsity: "Enough mentions a day",
  backtest: "Enough back-test windows",
};

export function ForecastsPage({ watchlists }: { watchlists: Watchlist[] }) {
  const filters = useFilters(watchlists);
  const [entityId, setEntityId] = useState<string | null>(null);
  const [forecasts, setForecasts] = useState<Forecast[] | null>(null);
  const [horizon, setHorizon] = useState(7);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { watchlist } = filters;
  const colorFor = useMemo(() => {
    const order = new Map(watchlist?.entities.map((e, i) => [e.id, i]));
    return (id: string) => seriesColor(order.get(id) ?? 0);
  }, [watchlist]);
  const entity = watchlist?.entities.find((e) => e.id === entityId) ?? watchlist?.entities[0];
  const forecast = forecasts?.find((f) => f.entity_id === entity?.id) ?? null;

  useEffect(() => {
    if (!watchlist) return;
    setForecasts(null);
    api.forecasts(watchlist.id).then(setForecasts).catch((e) => {
      setError(e instanceof Error ? e.message : "Could not load forecasts");
      setForecasts([]);
    });
  }, [watchlist]);

  async function rerun() {
    if (!entity) return;
    setRunning(true);
    setError(null);
    try {
      const fresh = await api.createForecast(entity.id, horizon);
      setForecasts((prev) => [...(prev ?? []).filter((f) => f.entity_id !== fresh.entity_id), fresh]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Forecast failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Forecasts"
        description="Estimated daily mentions for the coming days, with a range and how well the method did on past data."
        actions={
          watchlists.length > 1 && (
            <select value={watchlist?.id} onChange={(e) => { filters.setWatchlist(e.target.value); setEntityId(null); }}
              aria-label="Watchlist" className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm">
              {watchlists.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
          )
        }
      />

      {!watchlist || watchlist.entities.length === 0 ? (
        <EmptyState title="Nothing tracked yet">
          <Link to="/watchlists" className="font-medium text-indigo-700 underline">Create a watchlist</Link> and add data
          to see forecasts.
        </EmptyState>
      ) : (
        <>
          <div role="tablist" aria-label="Tracked term" className="mb-4 flex flex-wrap gap-2">
            {watchlist.entities.map((e) => {
              const selected = e.id === entity?.id;
              return (
                <button key={e.id} role="tab" aria-selected={selected} onClick={() => setEntityId(e.id)}
                  className={`flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm ${
                    selected ? "border-slate-900 bg-slate-900 text-white" : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                  }`}>
                  <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: colorFor(e.id) }} aria-hidden />
                  {e.term}
                </button>
              );
            })}
          </div>

          {error && <p className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

          {forecasts === null ? (
            <p className="py-10 text-center text-sm text-slate-500">Loading…</p>
          ) : !forecast ? (
            <EmptyState title={`No forecast for ${entity?.term} yet`}>
              Forecasts are made automatically after data is imported or synced. You can also run one now.
              <div className="mt-4"><RunControls horizon={horizon} setHorizon={setHorizon} running={running} onRun={rerun} /></div>
            </EmptyState>
          ) : forecast.status !== "ready" ? (
            <NotEnoughData forecast={forecast}>
              <RunControls horizon={horizon} setHorizon={setHorizon} running={running} onRun={rerun} />
            </NotEnoughData>
          ) : (
            <ForecastView forecast={forecast} color={colorFor(forecast.entity_id)}>
              <RunControls horizon={horizon} setHorizon={setHorizon} running={running} onRun={rerun} />
            </ForecastView>
          )}
        </>
      )}
    </>
  );
}

function RunControls({ horizon, setHorizon, running, onRun }: {
  horizon: number; setHorizon: (h: number) => void; running: boolean; onRun: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-center gap-2">
      <label className="text-sm text-slate-600" htmlFor="horizon">Days ahead</label>
      <select id="horizon" value={horizon} onChange={(e) => setHorizon(Number(e.target.value))}
        className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm">
        {[7, 14].map((h) => <option key={h} value={h}>{h}</option>)}
      </select>
      <button onClick={onRun} disabled={running}
        className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60">
        {running ? "Running…" : "Run forecast"}
      </button>
    </div>
  );
}

function NotEnoughData({ forecast, children }: { forecast: Forecast; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-amber-200 bg-amber-50 p-5">
      <h2 className="font-semibold text-amber-900">
        {forecast.status === "failed" ? "The forecast failed" : `Not enough reliable data to forecast ${forecast.term}`}
      </h2>
      <p className="mt-1 text-sm text-amber-900">
        A forecast is only shown when the data passes every check below, so a guess never looks like an estimate.
      </p>
      <Checks checks={forecast.checks} />
      <p className="mt-3 text-sm text-amber-900">
        Keep collecting: <Link to="/sources" className="font-medium underline">sync a source or upload more history</Link>, then run it again.
      </p>
      <div className="mt-4 flex justify-start">{children}</div>
    </section>
  );
}

function Checks({ checks }: { checks: Forecast["checks"] }) {
  return (
    <ul className="mt-3 space-y-1.5 text-sm">
      {checks.map((c) => (
        <li key={c.name} className="flex gap-2">
          <span aria-hidden className={c.passed ? "text-emerald-700" : "text-red-700"}>{c.passed ? "✓" : "✗"}</span>
          <span>
            <span className="font-medium">{CHECK_LABELS[c.name] ?? c.name}</span>
            <span className="sr-only">{c.passed ? " passed" : " failed"}</span>
            <span className="text-slate-600">: {c.detail}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

function ForecastView({ forecast, color, children }: { forecast: Forecast; color: string; children: ReactNode }) {
  const methods = forecast.backtest?.methods ?? [];
  const shown = methods.find((m) => m.name === forecast.method);
  const reference = methods.find((m) => m.name === "seasonal_naive");
  const total = forecast.points.reduce((s, p) => s + p.predicted, 0);
  const first = forecast.points[0]?.date;
  const lastDay = forecast.points.at(-1)?.date;

  return (
    <>
      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Tile label={`Estimated mentions, next ${forecast.horizon_days} days`} value={Math.round(total).toLocaleString()}
          note={first && lastDay ? `${shortDate(first)} to ${shortDate(lastDay)}, about ${(total / forecast.horizon_days).toFixed(1)} a day` : undefined} />
        <Tile label="Back-test error (WAPE)" value={pct(shown?.wape)}
          note={reference ? `Same day last week: ${pct(reference.wape)}` : undefined} />
        <Tile label="Method" value={forecast.method_label ?? "–"}
          note={forecast.candidate_beats_baseline
            ? "Exponential smoothing beat the same-day-last-week baseline"
            : "Exponential smoothing did not beat the same-day-last-week baseline"} />
      </div>

      <section className="mb-6 rounded-lg border border-slate-200 bg-white p-4">
        <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="font-semibold">Daily mentions of {forecast.term}</h2>
          <ForecastLegend color={color} level={forecast.interval_level} />
        </div>
        <p className="mb-3 text-xs text-slate-500">
          Last {forecast.history.length} collected days and the next {forecast.horizon_days}, UTC days. Gaps in the line were not collected.
          In past back-tests the {Math.round(forecast.interval_level * 100)}% range held the real value {pct(forecast.interval_coverage)} of the time.
        </p>
        <ForecastChart forecast={forecast} color={color} />
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="font-semibold">Back-test</h2>
          <p className="mb-3 text-xs text-slate-500">
            Each method forecast {forecast.backtest?.horizon_days} days ahead from {forecast.backtest?.origins.length} past
            dates ({forecast.backtest && shortDate(forecast.backtest.origins[0])} to {forecast.backtest && shortDate(forecast.backtest.origins.at(-1)!)}),
            using only data from before each date. Lower is better. The method with the lowest WAPE is shown.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                  <th className="py-2 pr-3 font-medium">Method</th>
                  <th className="py-2 pr-3 text-right font-medium">MAE</th>
                  <th className="py-2 pr-3 text-right font-medium">RMSE</th>
                  <th className="py-2 text-right font-medium">WAPE</th>
                </tr>
              </thead>
              <tbody>
                {methods.map((m) => (
                  <tr key={m.name} className={`border-b border-slate-100 ${m.name === forecast.method ? "font-medium" : ""}`}>
                    <td className="py-2 pr-3">
                      {m.label}
                      <span className="ml-2 text-xs font-normal text-slate-500">{m.kind}{m.name === forecast.method ? ", shown" : ""}</span>
                    </td>
                    <td className="py-2 pr-3 text-right tabular-nums">{m.mae?.toFixed(2) ?? "–"}</td>
                    <td className="py-2 pr-3 text-right tabular-nums">{m.rmse?.toFixed(2) ?? "–"}</td>
                    <td className="py-2 text-right tabular-nums">{pct(m.wape)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <details className="mt-3 text-sm">
            <summary className="cursor-pointer text-indigo-700">What these mean</summary>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-600">
              <li><b>MAE</b>: average number of mentions the forecast was off by on a day.</li>
              <li><b>RMSE</b>: like MAE but punishes big misses more.</li>
              <li><b>WAPE</b>: total error as a share of total mentions, so terms of different sizes can be compared.</li>
            </ul>
          </details>
          {shown && (
            <details className="mt-2 text-sm">
              <summary className="cursor-pointer text-indigo-700">Error by days ahead</summary>
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-slate-600">
                {shown.mae_by_horizon.map((v, i) => (
                  <span key={i} className="tabular-nums">Day {i + 1}: {v?.toFixed(1) ?? "–"}</span>
                ))}
              </div>
            </details>
          )}
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="font-semibold">Data checks</h2>
          <Checks checks={forecast.checks} />
          <p className="mt-4 text-xs text-slate-500">
            Forecast version {forecast.model_version}, made {new Date(forecast.created_at).toLocaleString()} from data
            {forecast.training_start && ` collected ${shortDate(forecast.training_start)} to ${shortDate(forecast.training_end!)}`}.
            Forecasts refresh automatically when new days are collected. Spikes from launches or viral posts can't be predicted.
          </p>
          <div className="mt-4 flex justify-start">{children}</div>
        </section>
      </div>
    </>
  );
}

function Tile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-sm text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
      {note && <div className="mt-1 text-xs text-slate-500">{note}</div>}
    </div>
  );
}
