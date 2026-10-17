import { api } from "../api/client";
import type { Filters } from "../hooks/useFilters";

/** Daily totals per term and source for the current filters. Counts and shares only, never post text. */
export function ExportLink({ filters }: { filters: Filters }) {
  const { watchlist, start, end, sources } = filters;
  if (!watchlist || !start || !end) return null;
  return (
    <a href={api.exportUrl(watchlist.id, start, end, sources.length ? sources : undefined)} download
      className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
      Download daily totals (CSV)
    </a>
  );
}
