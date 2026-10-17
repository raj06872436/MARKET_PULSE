import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { pct, shortDate } from "../charts/format";
import { seriesColor } from "../charts/palette";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { SentimentPill } from "../components/RecordBits";
import { useFilters, useTermColors } from "../hooks/useFilters";
import type { Insight, InsightBatch, InsightFact, Watchlist } from "../types/api";

const STATUS_TEXT: Record<string, string> = {
  not_configured: "Claude writing is off for this installation, so these cards come from fixed templates.",
  not_requested: "These cards come from fixed templates.",
  "all rejected": "Claude's drafts all cited numbers the data doesn't support, so these cards come from fixed templates.",
};

export function InsightsPage({ watchlists }: { watchlists: Watchlist[] }) {
  const filters = useFilters(watchlists);
  const { watchlist } = filters;
  const colorFor = useTermColors(watchlist, seriesColor);
  const [batch, setBatch] = useState<InsightBatch | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function generate(useLlm: boolean) {
    if (!watchlist) return;
    setRunning(true);
    setError(null);
    try {
      setBatch(await api.generateInsights(watchlist.id, useLlm));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not write insights");
    } finally {
      setRunning(false);
    }
  }

  useEffect(() => {
    if (!watchlist) return;
    setBatch(null);
    setError(null);
    api.insights(watchlist.id).then((stored) => {
      // Nothing stored yet: write template cards straight away. Claude is only called on request.
      if (stored.insights.length === 0 && watchlist.entities.length > 0) return api.generateInsights(watchlist.id, false);
      return stored;
    }).then(setBatch).catch((e) => setError(e instanceof Error ? e.message : "Could not load insights"));
  }, [watchlist]);

  const termName = (id: string | null) => watchlist?.entities.find((e) => e.id === id)?.term ?? null;
  const first = batch?.insights[0];

  return (
    <>
      <PageHeader
        title="Insights"
        description="What changed in the last 7 collected days compared with the 7 before, each card backed by the numbers and posts it relies on."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {watchlists.length > 1 && (
              <select value={watchlist?.id} onChange={(e) => filters.setWatchlist(e.target.value)} aria-label="Watchlist"
                className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm">
                {watchlists.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </select>
            )}
            {batch?.llm_available && (
              <button onClick={() => generate(true)} disabled={running}
                className="rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50">
                {running ? "Writing…" : "Write with Claude"}
              </button>
            )}
            <button onClick={() => generate(false)} disabled={running || !watchlist?.entities.length}
              className={`rounded-md px-3 py-2 text-sm font-medium disabled:opacity-50 ${batch?.llm_available
                ? "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                : "bg-indigo-600 text-white hover:bg-indigo-700"}`}>
              {running && !batch?.llm_available ? "Refreshing…" : "Refresh"}
            </button>
          </div>
        }
      />

      {error && <p className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      {!watchlist || watchlist.entities.length === 0 ? (
        <EmptyState title="Nothing tracked yet">
          <Link to="/watchlists" className="font-medium text-indigo-700 underline">Create a watchlist</Link> and add data to see insights.
        </EmptyState>
      ) : batch === null ? (
        <p className="py-10 text-center text-sm text-slate-500">{error ? "" : "Loading…"}</p>
      ) : batch.insights.length === 0 ? (
        <EmptyState title="No data collected yet">
          <Link to="/sources" className="font-medium text-indigo-700 underline">Upload a CSV or connect a source</Link> to see insights here.
        </EmptyState>
      ) : (
        <>
          <div className="mb-4 rounded-md bg-slate-100 px-3 py-2 text-sm text-slate-600" aria-live="polite">
            {first && <>Covering {shortDate(first.period_start)} to {shortDate(first.period_end)} (UTC), compared with {first.evidence.comparison
              ? `${shortDate(first.evidence.comparison.start)} to ${shortDate(first.evidence.comparison.end)}` : "the 7 days before"}. </>}
            {batch.generator === "llm"
              ? "Written by Claude from the numbers below; every number was checked against the data before showing."
              : batch.llm_status.startsWith("failed")
                ? `Claude couldn't be used (${batch.llm_status.replace("failed: ", "")}), so these cards come from fixed templates.`
                : STATUS_TEXT[batch.llm_status] ?? ""}
            {batch.rejected.length > 0 && ` ${batch.rejected.length} draft${batch.rejected.length > 1 ? "s were" : " was"} left out for stating unsupported numbers.`}
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            {batch.insights.map((card) => (
              <InsightCardView key={card.id} card={card} term={termName(card.entity_id)}
                color={card.entity_id ? colorFor(card.entity_id) : undefined} watchlistId={watchlist.id} />
            ))}
          </div>
        </>
      )}
    </>
  );
}

function formatFact(f: InsightFact): string {
  if (f.value === null) return "–";
  if (typeof f.value === "string") return f.value.replace(/_/g, " ");
  if (f.unit === "percent") return pct(f.value);
  if (f.unit === "score") return f.value.toFixed(1);
  return f.value.toLocaleString();
}

function InsightCardView({ card, term, color, watchlistId }: {
  card: Insight; term: string | null; color?: string; watchlistId: string;
}) {
  const explore = new URLSearchParams({ wl: watchlistId, range: "custom", from: card.period_start, to: card.period_end });
  if (card.entity_id) explore.append("term", card.entity_id);
  return (
    <article className="flex flex-col rounded-lg border border-slate-200 bg-white p-4">
      <header className="mb-2 flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-sm font-medium text-slate-700">
          {color && <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: color }} aria-hidden />}
          {term ?? "Whole watchlist"}
        </span>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600"
          title={card.model_version}>{card.generator === "llm" ? "Written by Claude" : "Template"}</span>
      </header>
      <p className="font-medium text-slate-900">{card.observation}</p>
      {card.interpretation && (
        <div className="mt-3 text-sm">
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Possible explanation</div>
          <p className="text-slate-700">{card.interpretation}</p>
        </div>
      )}
      {card.caveat && (
        <div className="mt-3 text-sm">
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Caveat</div>
          <p className="text-slate-600">{card.caveat}</p>
        </div>
      )}
      {card.suggested_action && (
        <div className="mt-3 text-sm">
          <div className="text-xs font-medium uppercase tracking-wide text-slate-500">Next step</div>
          <p className="text-slate-700">{card.suggested_action}</p>
        </div>
      )}
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-indigo-700">Evidence ({card.evidence.facts.length} numbers
          {card.evidence.examples.length > 0 && `, ${card.evidence.examples.length} posts`})</summary>
        <dl className="mt-2 grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-xs">
          {card.evidence.facts.map((f) => (
            <div key={f.id} className="contents">
              <dt className="text-slate-600">{f.label}</dt>
              <dd className="text-right font-medium tabular-nums text-slate-900">{formatFact(f)}</dd>
            </div>
          ))}
        </dl>
        {card.evidence.examples.length > 0 && (
          <ul className="mt-3 space-y-2">
            {card.evidence.examples.map((e) => (
              <li key={e.id} className="rounded-md bg-slate-50 p-2 text-xs">
                <p className="text-slate-800">{e.text}</p>
                <div className="mt-1 flex flex-wrap items-center gap-3 text-slate-500">
                  <SentimentPill label={e.sentiment} />
                  <span className="tabular-nums">{e.published_at}</span>
                  {e.url && <a href={e.url} target="_blank" rel="noreferrer" className="text-indigo-700 underline">open source</a>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </details>
      <div className="mt-auto pt-3 text-sm">
        <Link to={`/explore?${explore}`} className="font-medium text-indigo-700 underline">See these posts in Explore</Link>
      </div>
    </article>
  );
}
