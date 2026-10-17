import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { pct, shortDate } from "../charts/format";
import { SENTIMENT, seriesColor } from "../charts/palette";
import { SentimentLegend, SentimentShareChart } from "../charts/SentimentShareChart";
import { EmptyState } from "../components/EmptyState";
import { FilterBar } from "../components/FilterBar";
import { PageHeader } from "../components/PageHeader";
import { CoverageLabel, FLAG_LABELS, SentimentPill, coverageOf } from "../components/RecordBits";
import { SentimentBar, aspectLabel } from "../components/TrendCardView";
import { useFilters, useTermColors } from "../hooks/useFilters";
import type { EvidenceRecord, SentimentBreakdown, SeriesResponse, Watchlist } from "../types/api";

export function SentimentPage({ watchlists }: { watchlists: Watchlist[] }) {
  const filters = useFilters(watchlists, "90");
  const { watchlist, start, end, sources } = filters;
  const colorFor = useTermColors(watchlist, seriesColor);
  const entity = watchlist?.entities.find((e) => e.id === filters.termIds[0]) ?? watchlist?.entities[0];
  const [data, setData] = useState<SentimentBreakdown | null>(null);
  const [series, setSeries] = useState<SeriesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const src = sources.length ? sources : undefined;

  useEffect(() => {
    if (!entity || !start || !end) return;
    setData(null);
    setSeries(null);
    setError(null);
    api.sentiment(entity.id, start, end, src).then(setData).catch((e) => setError(e instanceof Error ? e.message : "Could not load sentiment"));
    api.series([entity.id], start, end, src).then(setSeries).catch(() => undefined);
  }, [entity?.id, start, end, sources.join()]);

  const explore = (extra: Record<string, string>) => {
    const params = new URLSearchParams(window.location.search);
    params.delete("term");
    if (entity) params.append("term", entity.id);
    Object.entries(extra).forEach(([k, v]) => params.set(k, v));
    return `/explore?${params}`;
  };
  const coverage = series ? coverageOf(series.series.map((s) => s.points)) : null;
  const flagged = data ? Object.entries(data.flagged).sort((a, b) => b[1] - a[1]) : [];

  return (
    <>
      <PageHeader title="Sentiment" description="How people feel about each term over time, which topics drive it, and the posts behind it." />
      <FilterBar filters={filters} watchlists={watchlists} terms="single" colorFor={colorFor} />

      {!entity ? (
        <EmptyState title="Nothing tracked yet">
          <Link to="/watchlists" className="font-medium text-indigo-700 underline">Create a watchlist</Link> first.
        </EmptyState>
      ) : !start ? (
        <EmptyState title="No data collected yet">
          <Link to="/sources" className="font-medium text-indigo-700 underline">Add data</Link> to see sentiment.
        </EmptyState>
      ) : error ? (
        <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      ) : !data ? (
        <p className="py-10 text-center text-sm text-slate-500">Loading…</p>
      ) : (
        <>
          <div className="mb-6 grid gap-4 md:grid-cols-3">
            <div className="rounded-lg border border-slate-200 bg-white p-4 md:col-span-2">
              <div className="mb-2 text-sm text-slate-500">
                {data.scored.toLocaleString()} of {data.mentions.toLocaleString()} posts scored ({entity.term}, {shortDate(data.start)} to {shortDate(data.end)})
              </div>
              <SentimentBar counts={data.counts} />
            </div>
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="text-sm text-slate-500">Less certain labels</div>
              {flagged.length === 0 ? (
                <div className="mt-1 text-sm text-slate-700">None flagged</div>
              ) : (
                <ul className="mt-1 space-y-0.5 text-sm">
                  {flagged.map(([flag, n]) => (
                    <li key={flag} className="flex justify-between gap-2">
                      <span className="text-slate-700">{FLAG_LABELS[flag] ?? flag}</span>
                      <span className="tabular-nums text-slate-500">{n} ({pct(n / Math.max(data.scored, 1))})</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <section className="mb-6 rounded-lg border border-slate-200 bg-white p-4">
            <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-semibold">Sentiment over time</h2>
              <div className="flex flex-wrap items-center gap-3">
                <SentimentLegend />
                {coverage && <CoverageLabel {...coverage} />}
              </div>
            </div>
            <p className="mb-2 text-xs text-slate-500">
              Share of scored posts in each {series && series.series[0].points.length <= 21 ? "day" : "7-day period, counted back from the last day"}. Periods with fewer than 5 scored posts are left empty.
            </p>
            {series ? <SentimentShareChart points={series.series[0].points} /> : <p className="py-10 text-center text-sm text-slate-500">Loading…</p>}
          </section>

          <div className="mb-6 grid gap-6 lg:grid-cols-2">
            <section className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="font-semibold">By topic</h2>
              <p className="mb-3 text-xs text-slate-500">
                Each topic mention is scored on its own clause, so one post can be positive about the camera and negative about the battery.
              </p>
              {data.aspects.length === 0 ? (
                <p className="text-sm text-slate-500">No topics found in this range.</p>
              ) : (
                <ul className="space-y-2.5">
                  {data.aspects.map((a) => (
                    <li key={a.aspect}>
                      <div className="mb-1 flex justify-between text-sm">
                        <Link to={explore({ aspect: a.aspect })} className="text-slate-800 hover:underline">{aspectLabel(a.aspect)}</Link>
                        <span className="tabular-nums text-xs text-slate-500">
                          {pct(a.negative / a.mentions)} negative, {pct(a.positive / a.mentions)} positive, n={a.mentions}
                        </span>
                      </div>
                      <div className="flex h-2 gap-0.5 overflow-hidden rounded-full" aria-hidden>
                        {(["negative", "neutral", "positive"] as const).filter((k) => a[k] > 0).map((k) => (
                          <div key={k} style={{ width: `${(a[k] / a.mentions) * 100}%`, background: SENTIMENT[k] }} />
                        ))}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="font-semibold">Frequent phrases</h2>
              <p className="mb-3 text-xs text-slate-500">Repeated word sequences in positive and in negative posts. Unreviewed, so read them as leads.</p>
              <div className="grid gap-4 sm:grid-cols-2">
                <Phrases title="In positive posts" color={SENTIMENT.positive} items={data.positive_phrases} />
                <Phrases title="In negative posts" color={SENTIMENT.negative} items={data.negative_phrases} />
              </div>
            </section>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Examples title="Positive examples" items={data.positive_examples} more={explore({ sentiment: "positive" })} />
            <Examples title="Negative examples" items={data.negative_examples} more={explore({ sentiment: "negative" })} />
          </div>
        </>
      )}
    </>
  );
}

function Phrases({ title, color, items }: { title: string; color: string; items: [string, number][] }) {
  return (
    <div>
      <h3 className="mb-1.5 flex items-center gap-1.5 text-sm font-medium">
        <span className="inline-block h-2 w-2 rounded-full" style={{ background: color }} aria-hidden />
        {title}
      </h3>
      {items.length === 0 ? (
        <p className="text-sm text-slate-500">None repeated</p>
      ) : (
        <ul className="space-y-0.5 text-sm">
          {items.map(([p, n]) => (
            <li key={p} className="flex justify-between gap-2">
              <span className="text-slate-800">"{p}"</span>
              <span className="tabular-nums text-slate-500">{n}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Examples({ title, items, more }: { title: string; items: EvidenceRecord[]; more: string }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-2 flex items-baseline justify-between">
        <h2 className="font-semibold">{title}</h2>
        <Link to={more} className="text-sm text-indigo-700 underline">See all in Explore</Link>
      </div>
      <p className="mb-2 text-xs text-slate-500">The most confident labels without quality flags.</p>
      {items.length === 0 ? (
        <p className="text-sm text-slate-500">None in this range.</p>
      ) : (
        <ul className="space-y-3">
          {items.map((r) => (
            <li key={r.id} className="text-sm">
              <p className="text-slate-900">{r.text ?? "text not stored"}</p>
              <div className="mt-1 flex flex-wrap items-center gap-x-3 text-xs text-slate-500">
                <SentimentPill label={r.sentiment} confidence={r.confidence} flags={r.flags} />
                <span>{r.published_at.slice(0, 10)}, {r.source}</span>
                {r.url && <a href={r.url} target="_blank" rel="noreferrer" className="text-indigo-700 underline">open source</a>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
