import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  useXAxisScale,
  useYAxisScale,
} from "recharts";

import type { EntitySeries, SeriesPoint } from "../types/api";
import { AXIS_TEXT, GRID } from "./palette";
import { shortDate } from "./format";

export interface LineSeries {
  key: string;
  label: string;
  color: string;
  points: SeriesPoint[];
}

type Row = Record<string, string | number | null> & { date: string };

interface Props {
  series: LineSeries[];
  value: (p: SeriesPoint) => number | null;
  format?: (v: number) => string;
  height?: number;
  yDomain?: [number, number];
}

/** Collapse consecutive days where every series is uncollected into shaded "not collected" bands. */
function missingSpans(dates: string[], series: LineSeries[]): [string, string][] {
  const spans: [string, string][] = [];
  let start: string | null = null;
  dates.forEach((date, i) => {
    const missing = series.every((s) => s.points[i]?.collection === "missing");
    if (missing && start === null) start = date;
    if ((!missing || i === dates.length - 1) && start !== null) {
      spans.push([start, missing ? date : dates[i - 1]]);
      start = null;
    }
  });
  return spans;
}

export function LineSeriesChart({ series, value, format = (v) => v.toLocaleString(), height = 280, yDomain }: Props) {
  const dates = series[0]?.points.map((p) => p.date) ?? [];
  const rows: Row[] = dates.map((date, i) => {
    const row: Row = { date };
    for (const s of series) row[s.key] = s.points[i] ? value(s.points[i]) : null;
    return row;
  });
  const spans = missingSpans(dates, series);

  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 136, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fontSize: 12, fill: AXIS_TEXT }} minTickGap={32} />
          <YAxis tick={{ fontSize: 12, fill: AXIS_TEXT }} width={44} domain={yDomain} tickFormatter={(v) => format(v)} />
          {spans.map(([a, b]) => (
            <ReferenceArea key={a} x1={a} x2={b} fill="#f0efec" fillOpacity={0.9} ifOverflow="extendDomain"
              label={{ value: "not collected", position: "insideTop", fontSize: 11, fill: AXIS_TEXT }} />
          ))}
          <Tooltip
            content={({ active, label }) => {
              if (!active || typeof label !== "string") return null;
              const i = dates.indexOf(label);
              return (
                <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow-sm">
                  <div className="mb-1 font-medium text-slate-700">{shortDate(label)} (UTC)</div>
                  {series.map((s) => {
                    const p = s.points[i];
                    const v = p ? value(p) : null;
                    return (
                      <div key={s.key} className="flex items-center gap-2">
                        <span className="inline-block h-2 w-2 rounded-full" style={{ background: s.color }} />
                        <span className="text-slate-600">{s.label}</span>
                        <span className="ml-auto pl-3 font-medium text-slate-900 tabular-nums">
                          {p?.collection === "missing" ? "not collected" : v === null ? "–" : format(v)}
                          {p?.collection === "incomplete" ? " (incomplete)" : ""}
                        </span>
                      </div>
                    );
                  })}
                </div>
              );
            }}
          />
          {series.length > 1 && (
            <Legend verticalAlign="top" align="left" wrapperStyle={{ paddingBottom: 8 }}
              content={() => (
                // Listed in watchlist order, the same order as the tooltip and the colours.
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-700">
                  {series.map((s) => (
                    <span key={s.key} className="flex items-center gap-1.5">
                      <svg width="14" height="4" aria-hidden><line x1="0" y1="2" x2="14" y2="2" stroke={s.color} strokeWidth="2" /></svg>
                      {s.label}
                    </span>
                  ))}
                </div>
              )}
            />
          )}
          {series.map((s) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={s.color}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 2, stroke: "#fff" }}
              connectNulls={false}
              isAnimationActive={false}
            />
          ))}
          {series.length <= 4 && <EndLabels rows={rows} series={series} />}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

const LABEL_GAP = 14;
const LABEL_MAX_CHARS = 20;

/**
 * Direct labels at the end of each line, nudged apart vertically so close
 * lines don't print on top of each other. Rendered inside the chart so it can
 * read the axis scales.
 */
function EndLabels({ rows, series }: { rows: Row[]; series: LineSeries[] }) {
  const xScale = useXAxisScale();
  const yScale = useYAxisScale();
  if (!xScale || !yScale) return null;
  const placed = series
    .map((s) => {
      const i = rows.findLastIndex((r) => r[s.key] !== null);
      if (i < 0) return null;
      const x = Number(xScale(rows[i].date));
      const y = Number(yScale(rows[i][s.key] as number));
      return Number.isFinite(x) && Number.isFinite(y) ? { s, x, y } : null;
    })
    .filter((p): p is { s: LineSeries; x: number; y: number } => p !== null)
    .sort((a, b) => a.y - b.y);
  // Push each label down until it clears the one above, then lift the whole
  // stack by half the bottom label's displacement so the nudge is shared.
  const ys = placed.map((p) => p.y);
  for (let i = 1; i < ys.length; i++) ys[i] = Math.max(ys[i], ys[i - 1] + LABEL_GAP);
  const overshoot = ys.length ? ys[ys.length - 1] - placed[placed.length - 1].y : 0;
  for (let i = 0; i < ys.length; i++) ys[i] -= overshoot / 2;
  return (
    <g>
      {placed.map((p, i) => {
        const text = p.s.label.length > LABEL_MAX_CHARS ? `${p.s.label.slice(0, LABEL_MAX_CHARS - 1)}…` : p.s.label;
        return (
          <text key={p.s.key} x={p.x + 8} y={ys[i]} dy={4} fontSize={12} fill="#0b0b0b">
            <title>{p.s.label}</title>
            {text}
          </text>
        );
      })}
    </g>
  );
}

export function toLineSeries(series: EntitySeries[], colorFor: (entityId: string) => string): LineSeries[] {
  return series.map((s) => ({ key: s.entity_id, label: s.term, color: colorFor(s.entity_id), points: s.points }));
}
