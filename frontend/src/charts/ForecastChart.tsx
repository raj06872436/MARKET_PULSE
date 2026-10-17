import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { Forecast } from "../types/api";
import { AXIS_TEXT, GRID } from "./palette";
import { shortDate } from "./format";

interface Row {
  date: string;
  observed: number | null;
  missing: boolean;
  predicted: number | null;
  band: [number, number] | null;
  actual: number | null;
}

/** Collected history as a solid line, the forecast as a dashed line with its range shaded, and
 * any actuals collected since the forecast as dots, so past forecasts can be checked by eye. */
export function ForecastChart({ forecast, color, height = 300 }: { forecast: Forecast; color: string; height?: number }) {
  const rows: Row[] = [
    ...forecast.history.map((h) => ({
      date: h.date, observed: h.mentions, missing: h.mentions === null, predicted: null, band: null, actual: null,
    })),
    ...forecast.points.map((p) => ({
      date: p.date,
      observed: null,
      missing: false,
      predicted: p.predicted,
      band: p.lower !== null && p.upper !== null ? ([p.lower, p.upper] as [number, number]) : null,
      actual: p.actual,
    })),
  ];
  // Join the dashed forecast line to the last collected day so there's no visual gap.
  const last = rows.findLast((r) => r.observed !== null);
  if (last && last.date === forecast.training_end) last.predicted = last.observed;

  const level = Math.round(forecast.interval_level * 100);
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 16, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fontSize: 12, fill: AXIS_TEXT }} minTickGap={32} />
          <YAxis tick={{ fontSize: 12, fill: AXIS_TEXT }} width={44} allowDecimals={false} />
          {forecast.training_end && (
            <ReferenceLine x={forecast.training_end} stroke={AXIS_TEXT} strokeDasharray="2 3"
              label={{ value: "forecast starts", position: "insideTopRight", fontSize: 11, fill: AXIS_TEXT, dy: -14 }} />
          )}
          <Area dataKey="band" stroke="none" activeDot={false} fill={color} fillOpacity={0.16} isAnimationActive={false} name={`${level}% range`} />
          <Line dataKey="observed" stroke={color} strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false} name="Collected" />
          <Line dataKey="predicted" stroke={color} strokeWidth={2} strokeDasharray="6 4" dot={false} isAnimationActive={false} name="Forecast" />
          <Scatter dataKey="actual" fill="#0b0b0b" isAnimationActive={false} name="Collected since" />
          <Tooltip
            content={({ active, label }) => {
              if (!active || typeof label !== "string") return null;
              const row = rows.find((r) => r.date === label);
              if (!row) return null;
              const isForecast = row.band !== null || (row.predicted !== null && row.observed === null);
              return (
                <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow-sm">
                  <div className="mb-1 font-medium text-slate-700">{shortDate(label)} (UTC)</div>
                  {isForecast ? (
                    <>
                      <div className="text-slate-600">
                        Estimated <span className="font-medium text-slate-900 tabular-nums">{row.predicted?.toFixed(1)}</span>
                      </div>
                      {row.band && (
                        <div className="text-slate-600">
                          {level}% range <span className="tabular-nums">{row.band[0].toFixed(1)} to {row.band[1].toFixed(1)}</span>
                        </div>
                      )}
                      {row.actual !== null && (
                        <div className="text-slate-600">
                          Collected since <span className="font-medium text-slate-900 tabular-nums">{row.actual}</span>
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="text-slate-600">
                      {row.missing ? "Not collected" : (
                        <>Mentions <span className="font-medium text-slate-900 tabular-nums">{row.observed}</span></>
                      )}
                    </div>
                  )}
                </div>
              );
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ForecastLegend({ color, level }: { color: string; level: number }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-600">
      <span className="flex items-center gap-1.5">
        <svg width="18" height="4" aria-hidden><line x1="0" y1="2" x2="18" y2="2" stroke={color} strokeWidth="2" /></svg>
        Collected
      </span>
      <span className="flex items-center gap-1.5">
        <svg width="18" height="4" aria-hidden><line x1="0" y1="2" x2="18" y2="2" stroke={color} strokeWidth="2" strokeDasharray="5 3" /></svg>
        Forecast (estimated)
      </span>
      <span className="flex items-center gap-1.5">
        <span className="inline-block h-3 w-4 rounded-sm" style={{ background: color, opacity: 0.25 }} aria-hidden />
        {Math.round(level * 100)}% range
      </span>
      <span className="flex items-center gap-1.5">
        <span className="inline-block h-2 w-2 rounded-full bg-[#0b0b0b]" aria-hidden />
        Collected since the forecast
      </span>
    </div>
  );
}
