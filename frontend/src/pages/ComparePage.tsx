import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { LineSeriesChart, toLineSeries } from "../charts/LineSeriesChart";
import { pct } from "../charts/format";
import { seriesColor } from "../charts/palette";
import { EmptyState } from "../components/EmptyState";
import { FilterBar } from "../components/FilterBar";
import { PageHeader } from "../components/PageHeader";
import { CoverageLabel } from "../components/RecordBits";
import { aspectLabel } from "../components/TrendCardView";
import { useFilters, useTermColors } from "../hooks/useFilters";
import type { Comparison, SeriesResponse, Watchlist } from "../types/api";

const MIN_CELL = 5;
const MAX_ASPECTS = 8;

export function ComparePage({ watchlists }: { watchlists: Watchlist[] }) {
  const filters = useFilters(watchlists);
  const { watchlist, start, end, sources } = filters;
  const colorFor = useTermColors(watchlist, seriesColor);
  const [data, setData] = useState<Comparison | null>(null);
  const [series, setSeries] = useState<SeriesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const src = sources.length ? sources : undefined;

  useEffect(() => {
    if (!watchlist || !start || !end || watchlist.entities.length === 0) return;
    setData(null);
    setSeries(null);
    setError(null);
    api.compare(watchlist.id, start, end, src).then(setData).catch((e) => setError(e instanceof Error ? e.message : "Could not load comparison"));
    api.series(watchlist.entities.map((e) => e.id), start, end, src).then(setSeries).catch(() => undefined);
  }, [watchlist, start, end, sources.join()]);

  const maxShare = Math.max(...(data?.scorecards.map((c) => c.share_of_voice ?? 0) ?? [0]), 0.0001);
  const aspects = data ? topAspects(data) : [];

  return (
    <>
      <PageHeader title="Compare" description="Your terms side by side over the same dates and sources, with how much of each was actually collected." />
      <FilterBar filters={filters} watchlists={watchlists} />

      {!watchlist || watchlist.entities.length < 2 ? (
        <EmptyState title="Add at least two terms to compare">
          <Link to="/watchlists" className="font-medium text-indigo-700 underline">Add a competitor</Link> to this watchlist.
        </EmptyState>
      ) : !start ? (
        <EmptyState title="No data collected yet">
          <Link to="/sources" className="font-medium text-indigo-700 underline">Add data</Link> to compare terms.
        </EmptyState>
      ) : error ? (
        <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      ) : !data ? (
        <p className="py-10 text-center text-sm text-slate-500">Loading…</p>
      ) : (
        <>
          <section className="mb-6 rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="mb-1 font-semibold">Scorecards</h2>
            <p className="mb-3 text-xs text-slate-500">
              A post that names two terms counts for both. Net sentiment is positive minus negative, as a share of scored posts.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[44rem] text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                    <th className="py-2 pr-3 font-medium">Term</th>
                    <th className="py-2 pr-3 text-right font-medium">Mentions</th>
                    <th className="py-2 pr-3 font-medium">Share of voice</th>
                    <th className="py-2 pr-3 text-right font-medium">Net sentiment</th>
                    <th className="py-2 pr-3 text-right font-medium">Negative</th>
                    <th className="py-2 pr-3 text-right font-medium">Engagement per post</th>
                    <th className="py-2 font-medium">Coverage</th>
                  </tr>
                </thead>
                <tbody>
                  {data.scorecards.map((c) => (
                    <tr key={c.entity_id} className="border-b border-slate-100">
                      <td className="py-2 pr-3">
                        <span className="flex items-center gap-2">
                          <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: colorFor(c.entity_id) }} aria-hidden />
                          <span>
                            {c.term}
                            <span className="block text-xs text-slate-500">{c.entity_type}</span>
                          </span>
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums">{c.mentions.toLocaleString()}</td>
                      <td className="py-2 pr-3">
                        <div className="flex items-center gap-2">
                          <div className="h-2 w-24 rounded-full bg-slate-100" aria-hidden>
                            <div className="h-2 rounded-full" style={{ width: `${((c.share_of_voice ?? 0) / maxShare) * 100}%`, background: colorFor(c.entity_id) }} />
                          </div>
                          <span className="tabular-nums">{pct(c.share_of_voice)}</span>
                        </div>
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums">
                        {c.net_sentiment === null ? "–" : `${c.net_sentiment > 0 ? "+" : ""}${Math.round(c.net_sentiment * 100)}`}
                        <span className="block text-xs text-slate-500">n={c.scored}</span>
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums">{pct(c.negative_share)}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">
                        {c.engagement_per_post === null ? "–" : c.engagement_per_post.toFixed(1)}
                        <span className="block text-xs text-slate-500">
                          {c.engagement_per_post === null ? "not given by source" : `from ${c.engagement_records} posts`}
                        </span>
                      </td>
                      <td className="py-2"><CoverageLabel days={data.days} collected={c.collected_days} incomplete={0} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="mb-6 rounded-lg border border-slate-200 bg-white p-4">
            <h2 className="mb-2 font-semibold">Daily mentions</h2>
            {series ? (
              <LineSeriesChart series={toLineSeries(series.series, colorFor)} value={(p) => p.mentions} />
            ) : (
              <p className="py-10 text-center text-sm text-slate-500">Loading…</p>
            )}
          </section>

          <div className="grid gap-6 lg:grid-cols-5">
            <section className="rounded-lg border border-slate-200 bg-white p-4 lg:col-span-3">
              <h2 className="mb-1 font-semibold">Share of negative posts by topic</h2>
              <p className="mb-3 text-xs text-slate-500">Darker means more of that term's posts on the topic were negative. Cells with fewer than {MIN_CELL} posts are left blank.</p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-slate-500">
                      <th className="py-1.5 pr-3 font-medium">Topic</th>
                      {data.scorecards.map((c) => <th key={c.entity_id} className="px-1 py-1.5 text-center font-medium">{c.term}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {aspects.map((a) => (
                      <tr key={a}>
                        <td className="py-1 pr-3 text-slate-700">{aspectLabel(a)}</td>
                        {data.scorecards.map((c) => {
                          const cell = c.aspects.find((x) => x.aspect === a);
                          if (!cell || cell.mentions < MIN_CELL) {
                            return <td key={c.entity_id} className="p-1 text-center text-xs text-slate-400">{cell ? `n=${cell.mentions}` : "–"}</td>;
                          }
                          const dark = cell.negative_share > 0.7; // white text only where the fill is dark enough to read it
                          return (
                            <td key={c.entity_id} className="p-0.5">
                              <div className={`rounded px-1.5 py-1 text-center tabular-nums ${dark ? "text-white" : "text-slate-900"}`}
                                style={{ background: `rgba(227, 73, 72, ${0.08 + cell.negative_share * 0.85})` }}
                                title={`${c.term}, ${aspectLabel(a)}: ${pct(cell.negative_share)} negative of ${cell.mentions}`}>
                                {pct(cell.negative_share)}
                                <span className={`block text-[11px] ${dark ? "text-white/90" : "text-slate-600"}`}>n={cell.mentions}</span>
                              </div>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="rounded-lg border border-slate-200 bg-white p-4 lg:col-span-2">
              <h2 className="mb-1 font-semibold">Where terms differ</h2>
              <p className="mb-3 text-xs text-slate-500">Topics where one term's share of negative posts is at least 15 points away from the others combined.</p>
              {data.aspect_gaps.length === 0 ? (
                <p className="text-sm text-slate-500">No clear differences in this range.</p>
              ) : (
                <ul className="space-y-2.5 text-sm">
                  {data.aspect_gaps.slice(0, 8).map((g) => (
                    <li key={`${g.entity_id}-${g.aspect}`} className="flex gap-2">
                      <span className="mt-1.5 inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: colorFor(g.entity_id) }} aria-hidden />
                      <span>
                        <b>{g.term}</b>: {pct(g.negative_share)} of {aspectLabel(g.aspect)} posts are negative, against {pct(g.others_negative_share)} for
                        the others ({g.difference > 0 ? "worse" : "better"}, {g.mentions} posts).
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </>
      )}
    </>
  );
}

function topAspects(data: Comparison): string[] {
  const totals = new Map<string, number>();
  for (const c of data.scorecards) for (const a of c.aspects) totals.set(a.aspect, (totals.get(a.aspect) ?? 0) + a.mentions);
  return [...totals.entries()].sort((a, b) => b[1] - a[1]).slice(0, MAX_ASPECTS).map(([a]) => a);
}
