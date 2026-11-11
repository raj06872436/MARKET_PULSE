import type { SourceStatus } from "../types/api";

const STYLES: Record<SourceStatus, { label: string; className: string }> = {
  not_connected: { label: "Not connected", className: "bg-slate-100 text-slate-600" },
  never_run: { label: "Not synced yet", className: "bg-slate-100 text-slate-600" },
  running: { label: "Syncing", className: "bg-indigo-50 text-indigo-700" },
  ok: { label: "Healthy", className: "bg-emerald-50 text-emerald-700" },
  degraded: { label: "Incomplete", className: "bg-amber-50 text-amber-800" },
  failed: { label: "Failed", className: "bg-red-50 text-red-700" },
};

export function StatusBadge({ status }: { status: SourceStatus }) {
  const style = STYLES[status];
  return <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ring-current/15 ${style.className}`}>{style.label}</span>;
}
