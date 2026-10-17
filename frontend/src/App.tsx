import { useCallback, useEffect, useState } from "react";
import { Route, Routes } from "react-router-dom";

import { api } from "./api/client";
import { Layout } from "./components/Layout";
import { OverviewPage } from "./pages/OverviewPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";
import { WatchlistsPage } from "./pages/WatchlistsPage";
import type { Watchlist, Workspace } from "./types/api";

// Authentication is not built yet, so the app uses the first workspace and creates one if none exists.
// The promise is shared so React's double-run of effects in development can't create two workspaces.
let workspacePromise: Promise<Workspace> | null = null;

function ensureWorkspace(): Promise<Workspace> {
  workspacePromise ??= api
    .listWorkspaces()
    .then((existing) => existing[0] ?? api.createWorkspace("My workspace"))
    .catch((e) => {
      workspacePromise = null;
      throw e;
    });
  return workspacePromise;
}

export default function App() {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    ensureWorkspace()
      .then(setWorkspace)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not reach the API"));
  }, []);

  const refresh = useCallback(async () => {
    if (workspace) setWatchlists(await api.listWatchlists(workspace.id));
  }, [workspace]);

  useEffect(() => {
    refresh().catch((e) => setError(e instanceof Error ? e.message : "Could not load watchlists"));
  }, [refresh]);

  if (error) {
    return (
      <div className="p-8 text-sm text-red-700">
        Could not connect to the MarketPulse API: {error}. Check that the backend is running on port 8000.
      </div>
    );
  }
  if (!workspace) return <div className="p-8 text-sm text-slate-500">Loading…</div>;

  return (
    <Layout workspaceName={workspace.name}>
      <Routes>
        <Route path="/" element={<OverviewPage watchlists={watchlists} />} />
        <Route
          path="/watchlists"
          element={<WatchlistsPage workspaceId={workspace.id} watchlists={watchlists} onChange={refresh} />}
        />
        <Route
          path="/compare"
          element={
            <PlaceholderPage
              title="Compare"
              description="Side-by-side brand comparison over matching date ranges and source coverage."
              note="Comparison needs daily aggregates, planned for weeks 5 and 6."
            />
          }
        />
        <Route
          path="/forecasts"
          element={
            <PlaceholderPage
              title="Forecasts"
              description="7-day attention forecasts with uncertainty ranges and back-test results."
              note="Forecasts are planned for weeks 5 and 6 and will only show once they beat a seasonal-naive baseline."
            />
          }
        />
        <Route
          path="/insights"
          element={
            <PlaceholderPage
              title="Insights"
              description="Evidence-linked summaries of what changed and why it may matter."
              note="Insight cards are planned for weeks 7 and 8."
            />
          }
        />
        <Route
          path="/sources"
          element={
            <PlaceholderPage
              title="Sources"
              description="Connector status, last successful sync and quota for each approved source."
              note="The CSV importer and first connector are planned for week 3, after the source feasibility check."
            />
          }
        />
      </Routes>
    </Layout>
  );
}
