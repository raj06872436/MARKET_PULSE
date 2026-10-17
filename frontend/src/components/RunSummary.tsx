import type { IngestionRun } from "../types/api";

export function formatTime(value: string | null): string {
  return value ? new Date(value).toLocaleString() : "never";
}

function count(value: number | null): string {
  return value === null ? "–" : value.toLocaleString();
}

export function RunCounts({ run }: { run: IngestionRun }) {
  const items: [string, number | null][] = [
    ["fetched", run.fetched_count],
    ["new", run.inserted_count],
    ["already stored", run.duplicate_count],
    ["matched a watchlist", run.matched_count],
  ];
  if (run.rejected_count) items.push(["rejected", run.rejected_count]);
  return (
    <dl className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
      {items.map(([label, value]) => (
        <div key={label} className="flex gap-1">
          <dt className="text-slate-500">{label}</dt>
          <dd className="font-medium">{count(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

export function CoverageNote({ run }: { run: IngestionRun }) {
  const coverage = run.coverage_json ?? {};
  const notes: string[] = [];
  const truncated = (coverage.truncated_queries as string[] | undefined) ?? [];
  const skipped = (coverage.skipped_queries as string[] | undefined) ?? [];
  if (coverage.no_terms) notes.push("No active watchlist terms, so nothing was searched.");
  if (truncated.length) notes.push(`Stopped at the page limit for: ${truncated.join(", ")}.`);
  if (skipped.length) notes.push(`Not searched (query limit reached): ${skipped.join(", ")}.`);
  if (typeof coverage.schema_errors === "number" && coverage.schema_errors > 0)
    notes.push(`${coverage.schema_errors} records were in an unexpected format and skipped.`);
  if (!notes.length) return null;
  return (
    <ul className="mt-2 list-disc pl-5 text-sm text-amber-800">
      {notes.map((n) => (
        <li key={n}>{n}</li>
      ))}
    </ul>
  );
}
