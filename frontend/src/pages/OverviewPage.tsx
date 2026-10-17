import { Link } from "react-router-dom";

import { TrendChart } from "../charts/TrendChart";
import { PageHeader } from "../components/PageHeader";
import type { Watchlist } from "../types/api";

export function OverviewPage({ watchlists }: { watchlists: Watchlist[] }) {
  const active = watchlists.filter((w) => w.active);
  const entityCount = watchlists.reduce((sum, w) => sum + w.entities.length, 0);

  return (
    <>
      <PageHeader title="Overview" description="Mention volume, sentiment and trend changes across your watchlists." />
      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Stat label="Active watchlists" value={active.length} />
        <Stat label="Tracked terms" value={entityCount} />
        <Stat label="Connected sources" value={0} />
      </div>
      {watchlists.length === 0 ? (
        <p className="mb-6 text-sm text-slate-600">
          Start by{" "}
          <Link to="/watchlists" className="font-medium text-indigo-700 underline">
            creating a watchlist
          </Link>{" "}
          with the brands and products you want to follow.
        </p>
      ) : null}
      <h2 className="mb-2 text-sm font-medium text-slate-600">Mention volume</h2>
      <TrendChart data={[]} label="Mentions" />
    </>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="text-sm text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
    </div>
  );
}
