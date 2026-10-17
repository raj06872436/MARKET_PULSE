import { useCallback, useEffect, useState } from "react";
import { Route, Routes } from "react-router-dom";

import { api } from "./api/client";
import { Layout } from "./components/Layout";
import { ComparePage } from "./pages/ComparePage";
import { ExplorePage } from "./pages/ExplorePage";
import { ForecastsPage } from "./pages/ForecastsPage";
import { InsightsPage } from "./pages/InsightsPage";
import { OverviewPage } from "./pages/OverviewPage";
import { SentimentPage } from "./pages/SentimentPage";
import { SourcesPage } from "./pages/SourcesPage";
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
        <Route path="/explore" element={<ExplorePage watchlists={watchlists} />} />
        <Route path="/sentiment" element={<SentimentPage watchlists={watchlists} />} />
        <Route path="/compare" element={<ComparePage watchlists={watchlists} />} />
        <Route path="/forecasts" element={<ForecastsPage watchlists={watchlists} />} />
        <Route path="/insights" element={<InsightsPage watchlists={watchlists} />} />
        <Route path="/sources" element={<SourcesPage />} />
      </Routes>
    </Layout>
  );
}
