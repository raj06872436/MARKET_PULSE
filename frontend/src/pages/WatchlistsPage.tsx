import { useState, type FormEvent } from "react";

import { api } from "../api/client";
import { AlertsPanel } from "../components/AlertsPanel";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import type { EntityType, Watchlist } from "../types/api";

const ENTITY_TYPES: EntityType[] = ["brand", "product", "keyword", "hashtag", "competitor"];

interface Props {
  workspaceId: string;
  watchlists: Watchlist[];
  onChange: () => Promise<void>;
}

export function WatchlistsPage({ workspaceId, watchlists, onChange }: Props) {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Returns whether the action succeeded, so forms keep the user's input on failure.
  async function run(action: () => Promise<unknown>): Promise<boolean> {
    setError(null);
    try {
      await action();
      await onChange();
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      return false;
    }
  }

  async function createWatchlist(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    if (await run(() => api.createWatchlist(workspaceId, name.trim()))) setName("");
  }

  return (
    <>
      <PageHeader
        title="Watchlists"
        description="Group the brands, products, hashtags and competitors you want to monitor."
      />
      <form onSubmit={createWatchlist} className="mb-6 grid gap-2 sm:flex">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Budget smartphones India"
          className="min-w-0 rounded-md border border-slate-300 px-3 py-2 text-sm sm:flex-1"
          aria-label="Watchlist name"
        />
        <button className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">
          Create watchlist
        </button>
      </form>
      {error && <p className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {watchlists.length === 0 ? (
        <EmptyState title="No watchlists yet">Create one above, then add the terms you want to track.</EmptyState>
      ) : (
        <div className="space-y-4">
          {watchlists.map((w) => (
            <WatchlistCard key={w.id} watchlist={w} run={run} />
          ))}
        </div>
      )}
    </>
  );
}

function WatchlistCard({ watchlist, run }: { watchlist: Watchlist; run: (a: () => Promise<unknown>) => Promise<boolean> }) {
  const [term, setTerm] = useState("");
  const [entityType, setEntityType] = useState<EntityType>("brand");
  const [variants, setVariants] = useState("");

  async function addEntity(event: FormEvent) {
    event.preventDefault();
    if (!term.trim()) return;
    const added = await run(() =>
      api.addEntity(watchlist.id, {
        term,
        entity_type: entityType,
        variants: variants.split(",").map((v) => v.trim()).filter(Boolean),
      }),
    );
    if (added) {
      setTerm("");
      setVariants("");
    }
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="font-semibold">{watchlist.name}</h2>
          <span
            className={`rounded-full px-2 py-0.5 text-xs ${
              watchlist.active ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"
            }`}
          >
            {watchlist.active ? "Active" : "Paused"}
          </span>
        </div>
        <div className="flex gap-2 text-sm">
          <button
            onClick={() => run(() => api.updateWatchlist(watchlist.id, { active: !watchlist.active }))}
            className="rounded-md border border-slate-300 px-3 py-1 hover:bg-slate-50"
          >
            {watchlist.active ? "Pause" : "Resume"}
          </button>
          <button
            onClick={() => run(() => api.deleteWatchlist(watchlist.id))}
            className="rounded-md border border-red-200 px-3 py-1 text-red-700 hover:bg-red-50"
          >
            Delete
          </button>
        </div>
      </div>

      {watchlist.entities.length > 0 ? (
        <ul className="mb-3 flex flex-wrap gap-2">
          {watchlist.entities.map((e) => (
            <li key={e.id} className="flex items-center gap-2 rounded-md bg-slate-100 px-2 py-1 text-sm">
              <span className="text-xs uppercase text-slate-600">{e.entity_type}</span>
              <span>{e.term}</span>
              {e.variants.length > 0 && <span className="text-slate-600">+{e.variants.length} {e.variants.length === 1 ? "variant" : "variants"}</span>}
              <button
                onClick={() => run(() => api.deleteEntity(watchlist.id, e.id))}
                aria-label={`Remove ${e.term}`}
                className="text-slate-600 hover:text-red-700"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mb-3 text-sm text-slate-500">No tracked terms yet.</p>
      )}

      <form onSubmit={addEntity} className="grid gap-2 sm:flex">
        <input
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          placeholder="Term, e.g. Redmi Note 14"
          className="min-w-0 rounded-md border border-slate-300 px-3 py-1.5 text-sm sm:flex-1"
          aria-label="Term"
        />
        <select
          value={entityType}
          onChange={(e) => setEntityType(e.target.value as EntityType)}
          className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          aria-label="Type"
        >
          {ENTITY_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <input
          value={variants}
          onChange={(e) => setVariants(e.target.value)}
          placeholder="Variants, comma separated"
          className="min-w-0 rounded-md border border-slate-300 px-3 py-1.5 text-sm sm:flex-1"
          aria-label="Variants"
        />
        <button className="rounded-md bg-slate-800 px-3 py-1.5 text-sm text-white hover:bg-slate-900">Add</button>
      </form>
      {watchlist.entities.length > 0 && <AlertsPanel watchlist={watchlist} />}
    </section>
  );
}
