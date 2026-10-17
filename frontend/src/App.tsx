import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { Route, Routes, useLocation } from "react-router-dom";

import { api, ApiError, SIGNED_OUT_EVENT } from "./api/client";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Layout } from "./components/Layout";
import { SignInPage } from "./pages/SignInPage";
import type { User, Watchlist, Workspace } from "./types/api";

// Pages load on demand, so the charting library isn't downloaded before the first chart is shown.
const page = <K extends string>(load: () => Promise<Record<K, React.ComponentType<any>>>, name: K) =>
  lazy(() => load().then((m) => ({ default: m[name] })));
const OverviewPage = page(() => import("./pages/OverviewPage"), "OverviewPage");
const ExplorePage = page(() => import("./pages/ExplorePage"), "ExplorePage");
const SentimentPage = page(() => import("./pages/SentimentPage"), "SentimentPage");
const ComparePage = page(() => import("./pages/ComparePage"), "ComparePage");
const ForecastsPage = page(() => import("./pages/ForecastsPage"), "ForecastsPage");
const InsightsPage = page(() => import("./pages/InsightsPage"), "InsightsPage");
const WatchlistsPage = page(() => import("./pages/WatchlistsPage"), "WatchlistsPage");
const SourcesPage = page(() => import("./pages/SourcesPage"), "SourcesPage");
const AccountPage = page(() => import("./pages/AccountPage"), "AccountPage");

// Every account gets a workspace when it is created; this only creates one if it was deleted.
// The promise is shared so React's double-run of effects in development can't create two.
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
  const [user, setUser] = useState<User | null | undefined>(undefined);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [error, setError] = useState<string | null>(null);
  const { pathname } = useLocation();

  const signedOut = useCallback(() => {
    workspacePromise = null;
    setUser(null);
    setWorkspace(null);
    setWatchlists([]);
  }, []);

  useEffect(() => {
    api.me().then(setUser).catch((e) => {
      if (e instanceof ApiError && e.status === 401) setUser(null);
      else setError(e instanceof Error ? e.message : "Could not reach the API");
    });
    window.addEventListener(SIGNED_OUT_EVENT, signedOut);
    return () => window.removeEventListener(SIGNED_OUT_EVENT, signedOut);
  }, [signedOut]);

  useEffect(() => {
    if (!user) return;
    ensureWorkspace()
      .then(setWorkspace)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load your workspace"));
  }, [user]);

  const refresh = useCallback(async () => {
    if (workspace) setWatchlists(await api.listWatchlists(workspace.id));
  }, [workspace]);

  useEffect(() => {
    refresh().catch((e) => setError(e instanceof Error ? e.message : "Could not load watchlists"));
  }, [refresh]);

  async function signOut() {
    await api.logout().catch(() => undefined);
    signedOut();
  }

  if (error) {
    return (
      <div role="alert" className="p-8 text-sm text-red-700">
        Could not connect to the MarketPulse API: {error}{" "}
        <button onClick={() => window.location.reload()} className="font-medium underline">Try again</button>
      </div>
    );
  }
  if (user === null) return <SignInPage onSignedIn={setUser} />;
  if (!user || !workspace) return <div className="p-8 text-sm text-slate-500" role="status">Loading…</div>;

  return (
    <Layout workspaceName={workspace.name} user={user} onSignOut={signOut}>
      <ErrorBoundary resetKey={pathname}>
        <Suspense fallback={<p className="py-10 text-center text-sm text-slate-500" role="status">Loading…</p>}>
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
            <Route path="/sources" element={<SourcesPage workspaceId={workspace.id} isAdmin={user.role === "admin"} />} />
            <Route path="/account" element={<AccountPage user={user} onSignedOut={signedOut} />} />
            <Route path="*" element={<p className="text-sm text-slate-600">That page doesn't exist. Pick one from the menu.</p>} />
          </Routes>
        </Suspense>
      </ErrorBoundary>
    </Layout>
  );
}
