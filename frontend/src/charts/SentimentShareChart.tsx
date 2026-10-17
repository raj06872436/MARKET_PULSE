import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { SeriesPoint } from "../types/api";
import { AXIS_TEXT, GRID, SENTIMENT } from "./palette";
import { shortDate } from "./format";

interface Bucket {
  start: string;
  end: string;
  positive: number;
  neutral: number;
  negative: number;
  scored: number;
  missing: number;
}

const MIN_N = 5;

/** Group daily points into buckets of `size` days counted back from the last day, so the newest bucket is complete. */
export function bucketSentiment(points: SeriesPoint[], size: number): Bucket[] {
  const buckets: Bucket[] = [];
  for (let endIdx = points.length - 1; endIdx >= 0; endIdx -= size) {
    const slice = points.slice(Math.max(0, endIdx - size + 1), endIdx + 1);
    const b: Bucket = { start: slice[0].date, end: slice.at(-1)!.date, positive: 0, neutral: 0, negative: 0, scored: 0, missing: 0 };
    for (const p of slice) {
      if (p.collection === "missing") b.missing += 1;
      b.positive += Math.round((p.positive_share ?? 0) * p.scored);
      b.neutral += Math.round((p.neutral_share ?? 0) * p.scored);
      b.negative += Math.round((p.negative_share ?? 0) * p.scored);
      b.scored += p.scored;
    }
    buckets.unshift(b);
  }
  return buckets;
}

/** Share of positive, neutral and negative posts per bucket, as 100% stacked bars. */
export function SentimentShareChart({ points, height = 260 }: { points: SeriesPoint[]; height?: number }) {
  const size = points.length <= 21 ? 1 : 7;
  const data = bucketSentiment(points, size).map((b) => ({
    ...b,
    // Buckets with too few scored posts are drawn empty rather than as a misleading 100%.
    pos: b.scored >= MIN_N ? b.positive / b.scored : null,
    neu: b.scored >= MIN_N ? b.neutral / b.scored : null,
    neg: b.scored >= MIN_N ? b.negative / b.scored : null,
  }));
  const latest = data.findLast((b) => b.pos !== null);
  const summary = latest
    ? `Share of scored posts by sentiment, ${size === 1 ? "per day" : "per week"}. Latest ${size === 1 ? "day" : "week"} with enough posts ` +
      `(${shortDate(latest.start)}${size === 1 ? "" : ` to ${shortDate(latest.end)}`}): ${Math.round(latest.pos! * 100)}% positive, ` +
      `${Math.round(latest.neu! * 100)}% neutral, ${Math.round(latest.neg! * 100)}% negative, from ${latest.scored} posts.`
    : "Not enough scored posts to show sentiment shares.";
  return (
    <figure style={{ height }} className="w-full">
      <figcaption className="sr-only">{summary}</figcaption>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} barCategoryGap={size === 1 ? 2 : 6}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="start" tickFormatter={shortDate} tick={{ fontSize: 12, fill: AXIS_TEXT }} minTickGap={24} />
          <YAxis tick={{ fontSize: 12, fill: AXIS_TEXT }} width={44} domain={[0, 1]} ticks={[0, 0.25, 0.5, 0.75, 1]}
            tickFormatter={(v) => `${Math.round(v * 100)}%`} />
          <Tooltip
            cursor={{ fill: "#f0efec" }}
            content={({ active, payload }) => {
              const b = active && payload?.[0]?.payload as (typeof data)[number] | undefined;
              if (!b) return null;
              return (
                <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow-sm">
                  <div className="mb-1 font-medium text-slate-700">
                    {size === 1 ? shortDate(b.start) : `${shortDate(b.start)} to ${shortDate(b.end)}`} (UTC)
                  </div>
                  {b.scored < MIN_N ? (
                    <div className="text-slate-600">{b.scored} scored posts, too few to show shares</div>
                  ) : (
                    (["positive", "neutral", "negative"] as const).map((k) => (
                      <div key={k} className="flex items-center gap-2">
                        <span className="inline-block h-2 w-2 rounded-full" style={{ background: SENTIMENT[k] }} />
                        <span className="text-slate-600">{k}</span>
                        <span className="ml-auto pl-3 font-medium text-slate-900 tabular-nums">
                          {Math.round((b[k] / b.scored) * 100)}% ({b[k]})
                        </span>
                      </div>
                    ))
                  )}
                  {b.missing > 0 && <div className="mt-1 text-amber-800">{b.missing} day{b.missing > 1 ? "s" : ""} not collected</div>}
                </div>
              );
            }}
          />
          <Bar dataKey="neg" stackId="s" fill={SENTIMENT.negative} stroke="#fff" strokeWidth={1} isAnimationActive={false} name="negative" />
          <Bar dataKey="neu" stackId="s" fill={SENTIMENT.neutral} stroke="#fff" strokeWidth={1} isAnimationActive={false} name="neutral" />
          <Bar dataKey="pos" stackId="s" fill={SENTIMENT.positive} stroke="#fff" strokeWidth={1} isAnimationActive={false} name="positive" />
        </BarChart>
      </ResponsiveContainer>
    </figure>
  );
}

export function SentimentLegend() {
  return (
    <div className="flex flex-wrap gap-3 text-xs text-slate-600">
      {(["positive", "neutral", "negative"] as const).map((k) => (
        <span key={k} className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: SENTIMENT[k] }} aria-hidden />
          {k}
        </span>
      ))}
    </div>
  );
}
