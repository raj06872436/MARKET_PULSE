import { useCallback, useEffect, useState, type FormEvent } from "react";

import { api } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { CoverageNote, formatTime, RunCounts } from "../components/RunSummary";
import { StatusBadge } from "../components/StatusBadge";
import type { CsvImportResult, IngestionRun, Source } from "../types/api";

const POLL_MS = 1500;

export function SourcesPage() {
  const [sources, setSources] = useState<Source[] | null>(null);
  const [runs, setRuns] = useState<IngestionRun[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [s, r] = await Promise.all([api.listSources(), api.listJobs(15)]);
    setSources(s);
    setRuns(r);
  }, []);

  useEffect(() => {
    refresh().catch((e) => setError(e instanceof Error ? e.message : "Could not load sources"));
  }, [refresh]);

  // While anything is syncing, keep polling so the status updates on its own.
  const syncing = sources?.some((s) => s.status === "running");
  useEffect(() => {
    if (!syncing) return;
    const timer = setInterval(() => refresh().catch(() => undefined), POLL_MS);
    return () => clearInterval(timer);
  }, [syncing, refresh]);

  async function act(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    }
    await refresh().catch(() => undefined);
  }

  const apiSources = sources?.filter((s) => s.kind === "api") ?? [];
  const csvSources = sources?.filter((s) => s.kind === "csv") ?? [];

  return (
    <>
      <PageHeader
        title="Sources"
        description="Where your data comes from, whether each source is healthy, and what the last sync actually covered."
      />
      {error && <p className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <h2 className="mb-2 text-sm font-medium text-slate-600">Connected platforms</h2>
      <div className="mb-8 space-y-4">
        {apiSources.map((s) => (
          <ApiSourceCard key={s.source} source={s} act={act} />
        ))}
      </div>

      <h2 className="mb-2 text-sm font-medium text-slate-600">CSV uploads</h2>
      <CsvUpload onDone={() => refresh().catch(() => undefined)} />
      {csvSources.length > 0 && (
        <div className="mt-4 space-y-3">
          {csvSources.map((s) => (
            <SourceSummary key={s.source} source={s} />
          ))}
        </div>
      )}

      <h2 className="mt-8 mb-2 text-sm font-medium text-slate-600">Recent runs</h2>
      {runs.length === 0 ? (
        <EmptyState title="No runs yet">Sync a platform or upload a CSV to see runs here.</EmptyState>
      ) : (
        <RunsTable runs={runs} />
      )}
    </>
  );
}

function SourceSummary({ source }: { source: Source }) {
  const run = source.last_run;
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold">{source.label}</span>
        <StatusBadge status={source.status} />
        <span className="text-sm text-slate-500">{source.record_count.toLocaleString()} records stored</span>
      </div>
      <div className="mt-1 text-sm text-slate-500">Last successful run: {formatTime(source.last_success_at)}</div>
      {run && (
        <div className="mt-2">
          {/* A failed run that fetched nothing has no counts worth showing; zeros would read as "no mentions". */}
          {(run.status !== "failed" || (run.fetched_count ?? 0) > 0) && <RunCounts run={run} />}
          {run.status === "failed" && (
            <p className="mt-2 text-sm text-red-700">
              Last run failed ({run.error_code}): {run.error_detail}
            </p>
          )}
          <CoverageNote run={run} />
        </div>
      )}
    </div>
  );
}

function ApiSourceCard({ source, act }: { source: Source; act: (a: () => Promise<unknown>) => Promise<void> }) {
  const [confirmed, setConfirmed] = useState(false);
  const [notes, setNotes] = useState("");
  const reviewed = source.policy_reviewed_at !== null;

  return (
    <div className="space-y-3">
      <SourceSummary source={source} />
      <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm">
        {source.notes.map((n) => (
          <p key={n} className="mb-1 text-slate-600">
            {n}
          </p>
        ))}
        {reviewed && (
          <p className="mb-3 text-slate-500">
            Terms reviewed {formatTime(source.policy_reviewed_at)}
            {source.policy_notes ? `: ${source.policy_notes}` : ""}
          </p>
        )}
        {source.enabled ? (
          <div className="flex flex-wrap gap-2">
            <button
              disabled={source.status === "running"}
              onClick={() => act(() => api.syncSource(source.source))}
              className="rounded-md bg-indigo-600 px-3 py-1.5 font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {source.status === "running" ? "Syncing…" : "Sync now"}
            </button>
            <button
              onClick={() => act(() => api.updateSource(source.source, { enabled: false }))}
              className="rounded-md border border-slate-300 px-3 py-1.5 hover:bg-slate-50"
            >
              Disconnect
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            <label className="flex items-start gap-2">
              <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} className="mt-1" />
              <span>
                I've checked {source.label}'s current terms, rate limits and retention rules, and this use is allowed.
              </span>
            </label>
            <input
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Review notes (optional), e.g. link to the terms you checked"
              className="w-full rounded-md border border-slate-300 px-3 py-1.5"
              aria-label="Review notes"
            />
            <button
              disabled={!confirmed && !reviewed}
              onClick={() =>
                act(() =>
                  api.updateSource(source.source, {
                    enabled: true,
                    ...(confirmed ? { policy_reviewed: true, policy_notes: notes } : {}),
                  }),
                )
              }
              className="rounded-md bg-slate-800 px-3 py-1.5 font-medium text-white hover:bg-slate-900 disabled:opacity-50"
            >
              Connect {source.label}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function CsvUpload({ onDone }: { onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [dataset, setDataset] = useState("");
  const [timezone, setTimezone] = useState("UTC");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<CsvImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file || !dataset.trim()) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.importCsv(file, dataset.trim(), timezone.trim() || "UTC"));
      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm">
      <p className="mb-3 text-slate-600">
        Upload data you're allowed to use. Required columns: <code>source_record_id</code>, <code>published_at</code>,{" "}
        <code>text</code>. Optional: <code>url</code>, <code>language</code>, <code>likes</code>, <code>comments</code>,{" "}
        <code>shares</code>, <code>views</code>. Uploading the same rows again won't double-count them.
      </p>
      <form onSubmit={submit} className="grid gap-2 sm:grid-cols-[1fr_1fr_10rem_auto]">
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          aria-label="CSV file"
          className="min-w-0 rounded-md border border-slate-300 px-2 py-1.5"
        />
        <input
          value={dataset}
          onChange={(e) => setDataset(e.target.value.toLowerCase())}
          placeholder="Dataset name, e.g. reviews-2026"
          aria-label="Dataset name"
          className="min-w-0 rounded-md border border-slate-300 px-3 py-1.5"
        />
        <input
          value={timezone}
          onChange={(e) => setTimezone(e.target.value)}
          aria-label="Timezone"
          title="Used for timestamps that have no UTC offset"
          className="min-w-0 rounded-md border border-slate-300 px-3 py-1.5"
        />
        <button
          disabled={busy || !file || !dataset.trim()}
          className="rounded-md bg-indigo-600 px-4 py-1.5 font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {busy ? "Importing…" : "Import"}
        </button>
      </form>
      {error && <p className="mt-3 rounded-md bg-red-50 px-3 py-2 text-red-700">{error}</p>}
      {result && (
        <div className="mt-3 rounded-md bg-slate-50 p-3">
          <RunCounts run={result.run} />
          {result.unknown_columns.length > 0 && (
            <p className="mt-2 text-slate-600">Ignored columns: {result.unknown_columns.join(", ")}</p>
          )}
          {result.errors.length > 0 && (
            <div className="mt-2">
              <p className="font-medium text-amber-800">
                {result.run.rejected_count} rows were rejected
                {result.run.rejected_count! > result.errors.length ? ` (first ${result.errors.length} shown)` : ""}:
              </p>
              <ul className="mt-1 list-disc pl-5 text-slate-700">
                {result.errors.map((e) => (
                  <li key={`${e.row}-${e.column}`}>
                    Row {e.row}
                    {e.column ? `, ${e.column}` : ""}: {e.message}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const RUN_STATUS: Record<IngestionRun["status"], string> = {
  queued: "text-slate-500",
  running: "text-indigo-700",
  succeeded: "text-emerald-700",
  partial: "text-amber-800",
  failed: "text-red-700",
};

function RunsTable({ runs }: { runs: IngestionRun[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="w-full min-w-[40rem] text-left text-sm">
        <thead className="border-b border-slate-200 text-slate-500">
          <tr>
            <th className="px-3 py-2 font-medium">Started</th>
            <th className="px-3 py-2 font-medium">Source</th>
            <th className="px-3 py-2 font-medium">Status</th>
            <th className="px-3 py-2 text-right font-medium">Fetched</th>
            <th className="px-3 py-2 text-right font-medium">New</th>
            <th className="px-3 py-2 text-right font-medium">Duplicates</th>
            <th className="px-3 py-2 text-right font-medium">Matched</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => {
            const blank = r.status === "failed" && !r.fetched_count;
            const cell = (value: number | null) => (blank || value === null ? "–" : value);
            return (
              <tr key={r.id} className="border-b border-slate-100 last:border-0">
                <td className="px-3 py-2 whitespace-nowrap">{formatTime(r.started_at)}</td>
                <td className="px-3 py-2">{r.source}</td>
                <td className={`px-3 py-2 ${RUN_STATUS[r.status]}`}>
                  {r.status}
                  {r.error_code ? ` (${r.error_code})` : ""}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{cell(r.fetched_count)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{cell(r.inserted_count)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{cell(r.duplicate_count)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{cell(r.matched_count)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
