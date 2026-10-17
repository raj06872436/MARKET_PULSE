import { type FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import { LineSeriesChart, toLineSeries } from "../charts/LineSeriesChart";
import { seriesColor } from "../charts/palette";
import { EmptyState } from "../components/EmptyState";
import { ExportLink } from "../components/ExportLink";
import { FilterBar } from "../components/FilterBar";
import { PageHeader } from "../components/PageHeader";
import { ASPECTS, CoverageLabel, SentimentPill, coverageOf } from "../components/RecordBits";
import { aspectLabel } from "../components/TrendCardView";
import { useFilters, useTermColors } from "../hooks/useFilters";
import type { RecordPage, RecordQuery, SeriesResponse, Watchlist } from "../types/api";

const PAGE_SIZE = 25;

export function ExplorePage({ watchlists }: { watchlists: Watchlist[] }) {
  const filters = useFilters(watchlists);
  const { watchlist, start, end, sources, termIds } = filters;
  const colorFor = useTermColors(watchlist, seriesColor);
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const sentiment = params.get("sentiment") ?? "";
  const aspect = params.get("aspect") ?? "";
  const sort = (params.get("sort") ?? "newest") as NonNullable<RecordQuery["sort"]>;
  const page = Number(params.get("page") ?? "0");

  const [draft, setDraft] = useState(q);
  const [records, setRecords] = useState<RecordPage | null>(null);
  const [series, setSeries] = useState<SeriesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selected = useMemo(
    () => (termIds.length ? termIds : watchlist?.entities.map((e) => e.id) ?? []),
    [termIds, watchlist],
  );
  const key = [watchlist?.id, start, end, sources.join(), selected.join()].join("|");

  useEffect(() => setDraft(q), [q]);

  useEffect(() => {
    if (!watchlist || !start || !end || selected.length === 0) return;
    setSeries(null);
    api.series(selected, start, end, sources.length ? sources : undefined).then(setSeries).catch(() => undefined);
  }, [key]);

  useEffect(() => {
    if (!watchlist || !start || !end) return;
    setRecords(null);
    setError(null);
    api.records({
      watchlistId: watchlist.id, start, end, entityIds: termIds, sources, q: q || undefined,
      sentiment: (sentiment || undefined) as RecordQuery["sentiment"], aspect: aspect || undefined, sort, limit: PAGE_SIZE, offset: page * PAGE_SIZE,
    }).then(setRecords).catch((e) => setError(e instanceof Error ? e.message : "Could not load posts"));
  }, [key, q, sentiment, aspect, sort, page]);

  function setParam(name: string, value: string) {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      if (value) next.set(name, value); else next.delete(name);
      if (name !== "page") next.delete("page");
      return next;
    }, { replace: true });
  }

  function search(e: FormEvent) {
    e.preventDefault();
    setParam("q", draft.trim());
  }

  const coverage = series ? coverageOf(series.series.map((s) => s.points)) : null;
  const from = records ? records.offset + 1 : 0;
  const to = records ? records.offset + records.items.length : 0;

  return (
    <>
      <PageHeader title="Explore" description="The posts behind every number, filtered by term, source, date, sentiment and topic."
        actions={<ExportLink filters={filters} />} />
      <FilterBar filters={filters} watchlists={watchlists} terms="multi" colorFor={colorFor} />

      {!watchlist || watchlist.entities.length === 0 ? (
        <EmptyState title="Nothing tracked yet">
          <Link to="/watchlists" className="font-medium text-indigo-700 underline">Create a watchlist</Link> to explore posts.
        </EmptyState>
      ) : !start ? (
        <EmptyState title="No data collected yet">
          <Link to="/sources" className="font-medium text-indigo-700 underline">Upload a CSV or connect a source</Link> to see posts here.
        </EmptyState>
      ) : (
        <>
          <section className="mb-6 rounded-lg border border-slate-200 bg-white p-4">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-semibold">Daily mentions</h2>
              {coverage && <CoverageLabel {...coverage} />}
            </div>
            {series ? (
              <LineSeriesChart series={toLineSeries(series.series, colorFor)} value={(p) => p.mentions} height={240} />
            ) : (
              <p className="py-10 text-center text-sm text-slate-500">Loading…</p>
            )}
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-4">
            <div className="mb-3 flex flex-wrap items-end gap-3">
              <form onSubmit={search} className="flex min-w-[14rem] flex-1 gap-2" role="search">
                <label htmlFor="post-search" className="sr-only">Search posts</label>
                <input id="post-search" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Search post text"
                  className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm" maxLength={200} />
                <button type="submit" className="rounded-md bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700">Search</button>
              </form>
              <Select label="Sentiment" value={sentiment} onChange={(v) => setParam("sentiment", v)}
                options={[["", "Any"], ["positive", "Positive"], ["neutral", "Neutral"], ["negative", "Negative"], ["unscored", "Not scored"]]} />
              <Select label="Topic" value={aspect} onChange={(v) => setParam("aspect", v)}
                options={[["", "Any"], ...ASPECTS.map((a) => [a, aspectLabel(a)] as [string, string])]} />
              <Select label="Sort" value={sort} onChange={(v) => setParam("sort", v)}
                options={[["newest", "Newest"], ["oldest", "Oldest"], ["engagement", "Most engagement"]]} />
            </div>

            {error && <p className="mb-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
            {!records ? (
              <p className="py-10 text-center text-sm text-slate-500">Loading…</p>
            ) : records.total === 0 ? (
              <p className="py-10 text-center text-sm text-slate-500">No posts match these filters.</p>
            ) : (
              <>
                <p className="mb-2 text-xs text-slate-500" aria-live="polite">
                  Showing {from} to {to} of {records.total.toLocaleString()} posts. A post naming two terms appears once.
                </p>
                <ul className="divide-y divide-slate-100 md:hidden">
                  {records.items.map((r) => (
                    <li key={r.id} className="py-3 text-sm">
                      <p className="text-slate-900">{r.text ?? <span className="text-slate-400">text not stored</span>}</p>
                      <div className="mt-1.5 flex flex-wrap items-start gap-x-3 gap-y-1 text-xs text-slate-500">
                        <SentimentPill label={r.sentiment} confidence={r.confidence} flags={r.flags} />
                        <span className="tabular-nums">{r.published_at.slice(0, 10)}</span>
                        <span>{r.terms.join(", ")}</span>
                        <span>engagement {r.engagement === null ? "not given" : r.engagement.toLocaleString()}</span>
                        {r.url && <a href={r.url} target="_blank" rel="noreferrer" className="text-indigo-700 underline">open source</a>}
                      </div>
                      {r.aspects.length > 0 && (
                        <div className="mt-1 text-xs text-slate-600">
                          {r.aspects.map((a) => `${aspectLabel(a.aspect)} (${a.sentiment})`).join(", ")}
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
                <div className="hidden overflow-x-auto md:block">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                        <th className="py-2 pr-3 font-medium">Date (UTC)</th>
                        <th className="py-2 pr-3 font-medium">Post</th>
                        <th className="py-2 pr-3 font-medium">Sentiment</th>
                        <th className="py-2 pr-3 font-medium">Topics</th>
                        <th className="py-2 text-right font-medium">Engagement</th>
                      </tr>
                    </thead>
                    <tbody>
                      {records.items.map((r) => (
                        <tr key={r.id} className="border-b border-slate-100 align-top">
                          <td className="py-2 pr-3 whitespace-nowrap text-slate-600 tabular-nums">
                            {r.published_at.slice(0, 10)}
                            <div className="text-[11px] text-slate-400">{r.source}</div>
                          </td>
                          <td className="py-2 pr-3">
                            <div className="text-slate-900">{r.text ?? <span className="text-slate-400">text not stored</span>}</div>
                            <div className="mt-0.5 flex flex-wrap gap-x-2 text-xs text-slate-500">
                              {r.terms.join(", ")}
                              {r.url && <a href={r.url} target="_blank" rel="noreferrer" className="text-indigo-700 underline">open source</a>}
                            </div>
                          </td>
                          <td className="py-2 pr-3"><SentimentPill label={r.sentiment} confidence={r.confidence} flags={r.flags} /></td>
                          <td className="py-2 pr-3 text-xs text-slate-600">
                            {r.aspects.length ? r.aspects.map((a) => `${aspectLabel(a.aspect)} (${a.sentiment})`).join(", ") : "–"}
                          </td>
                          <td className="py-2 text-right tabular-nums text-slate-700">
                            {r.engagement === null ? <span className="text-xs text-slate-400">not given</span> : r.engagement.toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="mt-3 flex items-center justify-end gap-2">
                  <button disabled={page === 0} onClick={() => setParam("page", String(page - 1))}
                    className="rounded-md border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-40">Previous</button>
                  <button disabled={to >= records.total} onClick={() => setParam("page", String(page + 1))}
                    className="rounded-md border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-40">Next</button>
                </div>
              </>
            )}
          </section>
        </>
      )}
    </>
  );
}

function Select({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void; options: [string, string][];
}) {
  const id = `filter-${label.toLowerCase()}`;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-xs text-slate-500">{label}</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm">
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </div>
  );
}
