export function Loading({ label = "Loading…", className = "py-12" }: { label?: string; className?: string }) {
  return (
    <div role="status" className={`flex items-center justify-center gap-2.5 text-sm text-slate-500 ${className}`}>
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-indigo-500" aria-hidden />
      {label}
    </div>
  );
}
