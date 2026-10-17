import { SENTIMENT } from "../charts/palette";
import type { SentimentLabel } from "../types/api";

export const ASPECTS = [
  "price", "battery", "camera", "display", "performance", "build_quality",
  "software", "delivery", "customer_support", "design", "connectivity",
];

export const FLAG_LABELS: Record<string, string> = {
  mixed: "mixed",
  sarcasm_cue: "possible sarcasm",
  low_signal: "few sentiment words",
  low_confidence: "low confidence",
  unsupported_script: "unsupported language",
};

export function SentimentPill({ label, confidence, flags = [] }: {
  label: string | null; confidence?: number | null; flags?: string[];
}) {
  if (!label) return <span className="text-xs text-slate-400">not scored</span>;
  const uncertain = flags.length > 0;
  return (
    <span className="inline-flex flex-col">
      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-800">
        <span className="inline-block h-2 w-2 rounded-full" style={{ background: SENTIMENT[label as SentimentLabel] ?? SENTIMENT.neutral }} aria-hidden />
        {label}
        {confidence !== null && confidence !== undefined && (
          <span className="font-normal text-slate-500">{Math.round(confidence * 100)}%</span>
        )}
      </span>
      {uncertain && <span className="text-[11px] text-slate-500">{flags.map((f) => FLAG_LABELS[f] ?? f).join(", ")}</span>}
    </span>
  );
}

export function coverageOf(points: { collection: string }[][]): { days: number; collected: number; incomplete: number } {
  const days = points[0]?.length ?? 0;
  let collected = 0;
  let incomplete = 0;
  for (let i = 0; i < days; i++) {
    const day = points.map((p) => p[i]?.collection);
    if (day.some((c) => c && c !== "missing")) collected += 1;
    if (day.some((c) => c === "incomplete")) incomplete += 1;
  }
  return { days, collected, incomplete };
}

export function CoverageLabel({ days, collected, incomplete }: { days: number; collected: number; incomplete: number }) {
  if (!days) return null;
  const full = collected === days && incomplete === 0;
  return (
    <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs ${full ? "bg-emerald-50 text-emerald-800" : "bg-amber-50 text-amber-900"}`}>
      <span aria-hidden>{full ? "✓" : "!"}</span>
      {collected} of {days} days collected{incomplete ? `, ${incomplete} incomplete` : ""}
    </span>
  );
}
