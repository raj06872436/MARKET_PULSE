import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import { addDays } from "../charts/format";
import type { DataRange, Watchlist } from "../types/api";

export const PRESETS = [
  { key: "7", label: "7 days", days: 7 },
  { key: "28", label: "28 days", days: 28 },
  { key: "90", label: "90 days", days: 90 },
  { key: "all", label: "All", days: null },
] as const;

// Filters shared by every page live in the URL, so they survive navigation and can be shared as links.
// wl = watchlist, range = preset key or "custom", from/to = custom dates, src = sources, term = tracked terms.
export const SHARED_PARAMS = ["wl", "range", "from", "to", "src"];

const rangeCache = new Map<string, Promise<DataRange>>();

function loadRange(watchlistId: string): Promise<DataRange> {
  if (!rangeCache.has(watchlistId)) {
    rangeCache.set(watchlistId, api.dataRange(watchlistId).catch((e) => {
      rangeCache.delete(watchlistId);
      throw e;
    }));
  }
  return rangeCache.get(watchlistId)!;
}

/** Forget cached data ranges, e.g. after an import adds newer days. */
export function invalidateDataRanges() {
  rangeCache.clear();
}

export interface Filters {
  watchlist: Watchlist | undefined;
  dataRange: DataRange | null;
  preset: string;
  start: string | null;
  end: string | null;
  sources: string[];
  termIds: string[];
  setWatchlist: (id: string) => void;
  setPreset: (key: string) => void;
  setCustom: (from: string, to: string) => void;
  setSources: (sources: string[]) => void;
  setTerms: (ids: string[]) => void;
}

export function useFilters(watchlists: Watchlist[], defaultPreset = "28"): Filters {
  const [params, setParams] = useSearchParams();
  const [dataRange, setDataRange] = useState<DataRange | null>(null);

  const wl = params.get("wl");
  const watchlist = watchlists.find((w) => w.id === wl) ?? watchlists.find((w) => w.active) ?? watchlists[0];

  useEffect(() => {
    setDataRange(null);
    if (watchlist) loadRange(watchlist.id).then(setDataRange).catch(() => setDataRange({ first: null, last: null, sources: [] }));
  }, [watchlist]);

  const preset = params.get("range") ?? defaultPreset;
  const from = params.get("from");
  const to = params.get("to");
  const sources = params.getAll("src");
  const termParam = params.getAll("term");

  const { start, end } = useMemo(() => {
    if (preset === "custom" && from && to) return { start: from, end: to };
    if (!dataRange?.first || !dataRange.last) return { start: null, end: null };
    const days = PRESETS.find((p) => p.key === preset)?.days;
    if (days === null) return { start: dataRange.first, end: dataRange.last };
    const start = addDays(dataRange.last, -((days ?? 28) - 1));
    return { start: start < dataRange.first ? dataRange.first : start, end: dataRange.last };
  }, [preset, from, to, dataRange]);

  const known = new Set(watchlist?.entities.map((e) => e.id));
  const termIds = termParam.filter((id) => known.has(id));

  function update(fn: (p: URLSearchParams) => void) {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      fn(next);
      next.delete("page");
      return next;
    }, { replace: true });
  }

  return {
    watchlist,
    dataRange,
    preset,
    start,
    end,
    sources,
    termIds,
    setWatchlist: (id) => update((p) => { p.set("wl", id); p.delete("term"); p.delete("src"); }),
    setPreset: (key) => update((p) => { p.set("range", key); p.delete("from"); p.delete("to"); }),
    setCustom: (f, t) => update((p) => { p.set("range", "custom"); p.set("from", f); p.set("to", t); }),
    setSources: (list) => update((p) => { p.delete("src"); list.forEach((s) => p.append("src", s)); }),
    setTerms: (ids) => update((p) => { p.delete("term"); ids.forEach((id) => p.append("term", id)); }),
  };
}

/** Colour follows the term's position in its watchlist, so it is the same on every page. */
export function useTermColors(watchlist: Watchlist | undefined, palette: (i: number) => string) {
  return useMemo(() => {
    const order = new Map(watchlist?.entities.map((e, i) => [e.id, i]));
    return (id: string) => palette(order.get(id) ?? 0);
  }, [watchlist, palette]);
}
