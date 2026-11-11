import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { isoDay, shortDate } from "../charts/format";
import { PRESETS, type Filters } from "../hooks/useFilters";
import type { Source, Watchlist } from "../types/api";

const STALE_AFTER_DAYS = 2;

interface Props {
  filters: Filters;
  watchlists: Watchlist[];
  terms?: "multi" | "single";
  colorFor?: (id: string) => string;
}

/** Shared filters in one row above the charts, plus the coverage and source-health notes every page needs. */
export function FilterBar({ filters, watchlists, terms, colorFor }: Props) {
  const { watchlist, dataRange, preset, start, end } = filters;
  const [failing, setFailing] = useState<Source[]>([]);
  const [customFrom, setCustomFrom] = useState(start ?? "");
  const [customTo, setCustomTo] = useState(end ?? "");

  useEffect(() => {
    api.listSources().then((s) => setFailing(s.filter((x) => x.status === "failed"))).catch(() => undefined);
  }, []);
  useEffect(() => {
    setCustomFrom(start ?? "");
    setCustomTo(end ?? "");
  }, [start, end]);

  const allSources = dataRange?.sources ?? [];
  const selectedTerms = terms === "single" ? [filters.termIds[0] ?? watchlist?.entities[0]?.id] : filters.termIds;
  const daysOld = dataRange?.last
    ? Math.floor((Date.parse(isoDay(new Date())) - Date.parse(dataRange.last)) / 86_400_000)
    : null;

  function toggleTerm(id: string) {
    if (terms === "single") return filters.setTerms([id]);
    const set = new Set(filters.termIds);
    if (set.has(id)) set.delete(id); else set.add(id);
    filters.setTerms([...set]);
  }

  function toggleSource(source: string) {
    const current = filters.sources.length ? filters.sources : allSources;
    const set = new Set(current);
    if (set.has(source)) set.delete(source); else set.add(source);
    // Every source selected is the same as no filter.
    filters.setSources(set.size === allSources.length ? [] : [...set]);
  }

  return (
    <div className="mb-6 space-y-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2.5 card px-3 py-3 sm:px-4">
        {watchlists.length > 1 && (
          <select value={watchlist?.id} onChange={(e) => filters.setWatchlist(e.target.value)} aria-label="Watchlist"
            className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm">
            {watchlists.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
          </select>
        )}
        <div role="group" aria-label="Date range" className="flex rounded-lg bg-slate-100 p-0.5">
          {PRESETS.map((p) => (
            <button key={p.key} onClick={() => filters.setPreset(p.key)} aria-pressed={preset === p.key}
              className={`rounded-md px-3 py-1 text-sm ${preset === p.key ? "bg-white font-medium text-slate-900 shadow-sm ring-1 ring-slate-200" : "text-slate-600 hover:text-slate-900"}`}>
              {p.label}
            </button>
          ))}
        </div>
        <form className="flex items-center gap-1.5 text-sm" onSubmit={(e) => {
          e.preventDefault();
          if (customFrom && customTo && customFrom <= customTo) filters.setCustom(customFrom, customTo);
        }}>
          <label className="sr-only" htmlFor="range-from">From</label>
          <input id="range-from" type="date" value={customFrom} min={dataRange?.first ?? undefined} max={customTo || undefined}
            onChange={(e) => setCustomFrom(e.target.value)} className="rounded-md border px-2 py-1" />
          <span className="text-slate-500">to</span>
          <label className="sr-only" htmlFor="range-to">To</label>
          <input id="range-to" type="date" value={customTo} min={customFrom || undefined}
            onChange={(e) => setCustomTo(e.target.value)} className="rounded-md border border-slate-300 px-2 py-1" />
          <button type="submit" className="rounded-md border border-slate-300 bg-white px-2.5 py-1 font-medium text-slate-700 shadow-xs hover:bg-slate-50">Apply</button>
        </form>
        {allSources.length > 1 && (
          <div role="group" aria-label="Sources" className="flex flex-wrap items-center gap-1.5 text-sm">
            <span className="text-slate-500">Sources</span>
            {allSources.map((s) => {
              const on = filters.sources.length === 0 || filters.sources.includes(s);
              return (
                <button key={s} onClick={() => toggleSource(s)} aria-pressed={on}
                  className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${on ? "border-indigo-200 bg-indigo-50 text-indigo-700" : "border-slate-200 bg-white text-slate-400 line-through"}`}>
                  {s}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {terms && watchlist && watchlist.entities.length > 0 && (
        <div role="group" aria-label="Tracked terms" className="flex flex-wrap gap-2">
          {watchlist.entities.map((e) => {
            const on = terms === "single" ? selectedTerms[0] === e.id : filters.termIds.length === 0 || filters.termIds.includes(e.id);
            return (
              <button key={e.id} onClick={() => toggleTerm(e.id)} aria-pressed={on}
                className={`flex items-center gap-2 rounded-full border px-3 py-1 text-sm shadow-xs ${
                  on ? "border-slate-800 bg-slate-800 font-medium text-white" : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900"
                }`}>
                {colorFor && <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: colorFor(e.id) }} aria-hidden />}
                {e.term}
              </button>
            );
          })}
          {terms === "multi" && filters.termIds.length > 0 && (
            <button onClick={() => filters.setTerms([])} className="px-2 text-sm text-indigo-700 underline">All terms</button>
          )}
        </div>
      )}

      {failing.length > 0 && (
        <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {failing.map((s) => s.label).join(", ")} failed on the last sync, so recent days may be missing rather than quiet.{" "}
          <Link to="/sources" className="font-medium underline">See sources</Link>
        </p>
      )}
      {daysOld !== null && daysOld > STALE_AFTER_DAYS && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          The latest collected day is {shortDate(dataRange!.last!)}, {daysOld} days ago. Ranges end there, not today.
        </p>
      )}
      {start && end && (
        <p className="text-xs text-slate-500">
          {shortDate(start)} to {shortDate(end)}, UTC days. Sources: {(filters.sources.length ? filters.sources : allSources).join(", ") || "none"}.
        </p>
      )}
    </div>
  );
}
