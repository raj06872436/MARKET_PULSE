import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { addDays, shortDate } from "../charts/format";
import { LineSeriesChart, toLineSeries } from "../charts/LineSeriesChart";
import { seriesColor } from "../charts/palette";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { useFilters } from "../hooks/useFilters";
import { TrendCardView } from "../components/TrendCardView";
import type { SeriesResponse, Source, TrendCard, Watchlist } from "../types/api";

const CHART_DAYS = 90;

export function OverviewPage({ watchlists }: { watchlists: Watchlist[] }) {
  const filters = useFilters(watchlists);
  const [sources, setSources] = useState<Source[]>([]);
  const [cards, setCards] = useState<TrendCard[] | null>(null);
  const [series, setSeries] = useState<SeriesResponse | null>(null);

  const { watchlist } = filters;
  // Colour follows the entity's position in its watchlist, so it stays the same on every page.
  const colorFor = useMemo(() => {
    const order = new Map(watchlist?.entities.map((e, i) => [e.id, i]));
    return (id: string) => seriesColor(order.get(id) ?? 0);
  }, [watchlist]);

  useEffect(() => {
    api.listSources().then(setSources).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!watchlist || watchlist.entities.length === 0) return;
    setCards(null);
    setSeries(null);
    api.trends(watchlist.id).then((result) => {
      setCards(result);
      const end = result.map((c) => c.sparkline.at(-1)?.date).filter(Boolean).sort().at(-1);
      if (end) {
        api.series(watchlist.entities.map((e) => e.id), addDays(end, -(CHART_DAYS - 1)), end).then(setSeries).catch(() => undefined);
      }
    }).catch(() => setCards([]));
  }, [watchlist]);

  const failing = sources.filter((s) => s.status === "failed");
  const connected = sources.filter((s) => s.status !== "not_connected").length;
  const weekMentions = cards?.reduce((sum, c) => sum + (c.evidence?.mentions ?? 0), 0);

  return (
    <>
      <PageHeader
        title="Overview"
        description="What changed in the last week for the brands and products you track."
        actions={
          watchlists.length > 1 && (
            <select value={watchlist?.id} onChange={(e) => filters.setWatchlist(e.target.value)} aria-label="Watchlist"
              className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm">
              {watchlists.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
          )
        }
      />
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Tracked terms" value={watchlist?.entities.length ?? 0} />
        <Stat label="Mentions in the last week" value={weekMentions ?? "–"} />
        <Stat label="Connected sources" value={connected} />
        <Stat label="Watchlists" value={watchlists.length} />
      </div>

      {failing.length > 0 && (
        <p className="mb-6 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {failing.map((s) => s.label).join(", ")} failed on the last sync, so recent numbers may be missing.{" "}
          <Link to="/sources" className="font-medium underline">See sources</Link>
        </p>
      )}

      {!watchlist || watchlist.entities.length === 0 ? (
        <EmptyState title="Nothing tracked yet">
          <Link to="/watchlists" className="font-medium text-indigo-700 underline">Create a watchlist</Link> with the brands and
          products you want to follow, then <Link to="/sources" className="font-medium text-indigo-700 underline">add data</Link>.
        </EmptyState>
      ) : (
        <>
          <section className="mb-8 rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="font-semibold">Daily mentions</h2>
            {series ? (
              <>
                <p className="mb-2 text-xs text-slate-500">
                  {shortDate(series.start)} to {shortDate(series.end)}, UTC days. Sources: {series.sources.join(", ") || "none"}. Shaded days were not collected.
                </p>
                <LineSeriesChart series={toLineSeries(series.series, colorFor)} value={(p) => p.mentions} />
              </>
            ) : cards && cards.every((c) => c.sparkline.length === 0) ? (
              <EmptyState title="No data collected yet">
                <Link to="/sources" className="font-medium text-indigo-700 underline">Upload a CSV or connect a source</Link> to see mentions here.
              </EmptyState>
            ) : (
              <p className="py-10 text-center text-sm text-slate-500">Loading…</p>
            )}
          </section>

          <h2 className="mb-3 font-semibold">Trends</h2>
          {cards && cards.length > 0 && (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {cards.map((c) => <TrendCardView key={c.entity_id} card={c} color={colorFor(c.entity_id)} />)}
            </div>
          )}
        </>
      )}
    </>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-sm text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{typeof value === "number" ? value.toLocaleString() : value}</div>
    </div>
  );
}
