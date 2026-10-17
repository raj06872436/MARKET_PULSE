import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { EmptyState } from "../components/EmptyState";

export interface SeriesPoint {
  date: string;
  // null means the source reported no data for that day, which is not the same as zero mentions.
  value: number | null;
}

export function TrendChart({ data, label }: { data: SeriesPoint[]; label: string }) {
  if (data.length === 0) {
    return (
      <EmptyState title="No data collected yet">
        Charts appear once a source has been connected and its first sync has finished.
      </EmptyState>
    );
  }
  return (
    <div className="h-64 rounded-lg border border-slate-200 bg-white p-4">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid stroke="#e2e8f0" vertical={false} />
          <XAxis dataKey="date" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} width={40} />
          <Tooltip />
          <Line type="monotone" dataKey="value" name={label} stroke="#4f46e5" strokeWidth={2} dot={false} connectNulls={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
