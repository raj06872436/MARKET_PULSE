import { SENTIMENT } from "../charts/palette";
import { pct, shortDate } from "../charts/format";
import { Sparkline } from "../charts/Sparkline";
import type { Evidence, TrendCard, TrendComponent } from "../types/api";

export const EXPLANATIONS: Record<string, string> = {
  rising_negative: "Mentions are rising and sentiment is getting worse",
  rising_mentions: "Mentions are rising",
  one_day_spike: "A one-day spike, not a sustained trend",
  falling_mentions: "Mentions are falling",
  sentiment_drop: "Sentiment is getting worse",
  sentiment_rise: "Sentiment is improving",
  stable: "No significant change",
  insufficient_data: "Not enough data to call a trend",
};

const COMPONENT_LABELS: Record<string, string> = {
  mention_growth: "Mention growth",
  engagement_growth: "Engagement growth",
  sentiment_shift: "Sentiment shift",
  persistence: "Persistence",
};

const CONFIDENCE_STYLE = {
  high: "bg-emerald-50 text-emerald-800",
  medium: "bg-amber-50 text-amber-800",
  low: "bg-slate-100 text-slate-600",
};

export function aspectLabel(aspect: string): string {
  return aspect.replace("_", " ");
}

function componentInputs(name: string, c: TrendComponent): string {
  if (c.value === null) return c.reason ?? "not enough data";
  switch (name) {
    case "mention_growth":
      return `${c.current_mentions} mentions this week vs ${c.previous_mentions} the week before`;
    case "engagement_growth":
      return `${c.current_per_post} vs ${c.previous_per_post} engagement per post`;
    case "sentiment_shift":
      return `net sentiment ${Number(c.current_net).toFixed(2)} vs ${Number(c.previous_net).toFixed(2)}, damped ×${c.damping} for sample size`;
    case "persistence":
      return `${c.days_above_baseline} of 7 days above the usual ${c.baseline_daily_mentions} a day`;
    default:
      return "";
  }
}

export function SentimentBar({ counts }: { counts: Evidence["sentiment"] }) {
  const total = counts.positive + counts.neutral + counts.negative;
  if (!total) return <p className="text-sm text-slate-500">No scored posts</p>;
  const parts = (["positive", "neutral", "negative"] as const).filter((k) => counts[k] > 0);
  return (
    <div>
      <div className="flex h-2.5 gap-0.5 overflow-hidden rounded-full" role="img"
        aria-label={`${counts.positive} positive, ${counts.neutral} neutral, ${counts.negative} negative`}>
        {parts.map((k) => (
          <div key={k} style={{ width: `${(counts[k] / total) * 100}%`, background: SENTIMENT[k] }} />
        ))}
      </div>
      <div className="mt-1 flex flex-wrap gap-x-3 text-xs text-slate-600">
        {(["positive", "neutral", "negative"] as const).map((k) => (
          <span key={k} className="flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: SENTIMENT[k] }} />
            {k} {pct(counts[k] / total)}
          </span>
        ))}
        <span className="text-slate-500">n={total}</span>
      </div>
    </div>
  );
}

export function TrendCardView({ card, color }: { card: TrendCard; color: string }) {
  const d = card.details;
  const ev = card.evidence;
  const growth = d?.components.mention_growth;
  return (
    <article className="flex flex-col rounded-lg border border-slate-200 bg-white p-4">
      <header className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: color }} />
            <h3 className="font-semibold">{card.term}</h3>
          </div>
          <p className="mt-0.5 text-xs uppercase tracking-wide text-slate-500">{card.entity_type}</p>
        </div>
        {card.score !== null && (
          <div className="text-right">
            <div className="text-2xl font-semibold tabular-nums">{Math.round(card.score)}</div>
            <div className="text-xs text-slate-500">trend score</div>
          </div>
        )}
      </header>

      <p className="mt-2 text-sm font-medium">{EXPLANATIONS[card.explanation_code ?? "insufficient_data"]}</p>
      {d && (
        <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <span className={`rounded-full px-2 py-0.5 font-medium ${CONFIDENCE_STYLE[d.confidence]}`}>{d.confidence} confidence</span>
          Week to {shortDate(d.window.end)} vs the week before (UTC)
        </p>
      )}

      <div className="mt-3">
        <Sparkline points={card.sparkline} color={color} label={card.term} />
        <p className="text-xs text-slate-500">Daily mentions, last 28 days</p>
      </div>

      {ev && (
        <div className="mt-3 space-y-3 border-t border-slate-100 pt-3 text-sm">
          <p>
            <span className="font-medium">{ev.mentions}</span> mentions this week
            {growth?.previous_mentions !== undefined && <span className="text-slate-500"> (previous week {String(growth.previous_mentions)})</span>}
          </p>
          <SentimentBar counts={ev.sentiment} />
          {ev.aspects.length > 0 && (
            <div>
              <p className="mb-1 text-xs font-medium text-slate-500">Most discussed</p>
              <ul className="space-y-0.5">
                {ev.aspects.slice(0, 3).map((a) => (
                  <li key={a.aspect} className="flex justify-between gap-2">
                    <span className="capitalize">{aspectLabel(a.aspect)}</span>
                    <span className="tabular-nums text-slate-600">
                      {a.mentions} · {pct(a.negative / a.mentions)} negative
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {ev.phrases.length > 0 && (
            <div>
              <p className="mb-1 text-xs font-medium text-slate-500">Frequent phrases (unreviewed)</p>
              <p className="text-slate-700">{ev.phrases.slice(0, 4).map(([p, c]) => `"${p}" (${c})`).join(", ")}</p>
            </div>
          )}
          {ev.examples.length > 0 && (
            <details>
              <summary className="cursor-pointer text-xs font-medium text-indigo-700">Example posts</summary>
              <ul className="mt-2 space-y-2">
                {ev.examples.map((e) => (
                  <li key={e.id} className="text-slate-700">
                    <span className="mr-1 rounded px-1 text-xs" style={{ background: e.sentiment ? `${SENTIMENT[e.sentiment as keyof typeof SENTIMENT]}33` : undefined }}>
                      {e.sentiment ?? "unscored"}
                    </span>
                    {e.url ? <a href={e.url} target="_blank" rel="noreferrer" className="underline decoration-slate-300">{e.text}</a> : e.text}
                    <span className="ml-1 text-xs text-slate-500">{shortDate(e.published_at.slice(0, 10))} · {e.source}</span>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {d && (
        <details className="mt-3 border-t border-slate-100 pt-3 text-sm">
          <summary className="cursor-pointer text-xs font-medium text-indigo-700">How this score is calculated</summary>
          <table className="mt-2 w-full text-left text-xs">
            <thead className="text-slate-500">
              <tr><th className="py-1 font-medium">Component</th><th className="py-1 text-right font-medium">Value</th><th className="py-1 text-right font-medium">Weight</th></tr>
            </thead>
            <tbody>
              {Object.entries(d.components).map(([name, c]) => (
                <tr key={name} className="border-t border-slate-100 align-top">
                  <td className="py-1 pr-2">
                    {COMPONENT_LABELS[name]}
                    <div className="text-slate-500">{componentInputs(name, c)}</div>
                  </td>
                  <td className="py-1 text-right tabular-nums">{c.value === null ? "–" : Math.round(c.value)}</td>
                  <td className="py-1 text-right tabular-nums">{pct(c.weight)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-slate-500">
            Each component is 0–100 where 50 means no change. Weighted average of available components, score version {d.version}. Starter weights, not validated constants.
          </p>
        </details>
      )}
    </article>
  );
}
