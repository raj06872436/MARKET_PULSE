import { Line, LineChart, ResponsiveContainer, YAxis } from "recharts";

import type { SeriesPoint } from "../types/api";

export function Sparkline({ points, color, label }: { points: SeriesPoint[]; color: string; label: string }) {
  const data = points.map((p) => ({ date: p.date, v: p.mentions }));
  const total = points.reduce((sum, p) => sum + (p.mentions ?? 0), 0);
  const missing = points.filter((p) => p.collection === "missing").length;
  return (
    <figure className="h-12 w-full" aria-label={`${label}: ${total} mentions over ${points.length} days${missing ? `, ${missing} days not collected` : ""}`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 2, bottom: 4, left: 2 }}>
          <YAxis hide domain={[0, "auto"]} />
          <Line type="monotone" dataKey="v" stroke={color} strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </figure>
  );
}
