import type {
  Alert,
  AlertEvent,
  AlertRule,
  CsvImportResult,
  InsightBatch,
  Comparison,
  DataRange,
  Evidence,
  Forecast,
  RecordPage,
  RecordQuery,
  SentimentBreakdown,
  SeriesResponse,
  TrendCard,
  IngestionRun,
  User,
  Source,
  TrackedEntity,
  TrackedEntityCreate,
  Watchlist,
  Workspace,
} from "../types/api";

/** Fired when the API says the session has ended, so the app can show the sign-in screen. */
export const SIGNED_OUT_EVENT = "marketpulse:signed-out";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isForm = init?.body instanceof FormData;
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      headers: isForm ? undefined : { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError(0, "Can't reach the MarketPulse server. Check your connection and try again.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail =
      typeof body?.detail === "string"
        ? body.detail
        : Array.isArray(body?.detail)
          ? body.detail.map((d: { msg?: string }) => d.msg).join("; ")
          : response.statusText;
    if (response.status === 401 && !path.startsWith("/auth/")) window.dispatchEvent(new Event(SIGNED_OUT_EVENT));
    throw new ApiError(response.status, detail);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export const api = {
  me: () => request<User>("/auth/me"),
  login: (email: string, password: string) =>
    request<User>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  register: (email: string, password: string) =>
    request<User>("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  deleteAccount: () => request<void>("/auth/me", { method: "DELETE" }),

  listWorkspaces: () => request<Workspace[]>("/workspaces"),
  createWorkspace: (name: string) =>
    request<Workspace>("/workspaces", { method: "POST", body: JSON.stringify({ name }) }),

  listWatchlists: (workspaceId: string) =>
    request<Watchlist[]>(`/watchlists?workspace_id=${encodeURIComponent(workspaceId)}`),
  createWatchlist: (workspaceId: string, name: string, language = "en") =>
    request<Watchlist>("/watchlists", {
      method: "POST",
      body: JSON.stringify({ workspace_id: workspaceId, name, language }),
    }),
  updateWatchlist: (id: string, patch: Partial<Pick<Watchlist, "name" | "language" | "active">>) =>
    request<Watchlist>(`/watchlists/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteWatchlist: (id: string) => request<void>(`/watchlists/${id}`, { method: "DELETE" }),

  addEntity: (watchlistId: string, body: TrackedEntityCreate) =>
    request<TrackedEntity>(`/watchlists/${watchlistId}/entities`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  deleteEntity: (watchlistId: string, entityId: string) =>
    request<void>(`/watchlists/${watchlistId}/entities/${entityId}`, { method: "DELETE" }),

  listSources: () => request<Source[]>("/sources"),
  updateSource: (source: string, body: { enabled?: boolean; policy_reviewed?: boolean; policy_notes?: string }) =>
    request<Source>(`/sources/${source}`, { method: "PUT", body: JSON.stringify(body) }),
  syncSource: (source: string) => request<IngestionRun>(`/sources/${source}/sync`, { method: "POST" }),
  getJob: (id: string) => request<IngestionRun>(`/jobs/${id}`),
  listJobs: (limit = 20) => request<IngestionRun[]>(`/jobs?limit=${limit}`),
  trends: (watchlistId: string) => request<TrendCard[]>(`/trends?watchlist_id=${watchlistId}`),
  series: (entityIds: string[], start: string, end: string, sources?: string[]) => {
    const params = new URLSearchParams({ entity_ids: entityIds.join(","), start, end });
    sources?.forEach((s) => params.append("source", s));
    return request<SeriesResponse>(`/metrics/series?${params}`);
  },
  dataRange: (watchlistId: string) => request<DataRange>(`/watchlists/${watchlistId}/data-range`),
  records: (q: RecordQuery) => {
    const params = new URLSearchParams({ watchlist_id: q.watchlistId, start: q.start, end: q.end });
    if (q.entityIds?.length) params.set("entity_ids", q.entityIds.join(","));
    q.sources?.forEach((s) => params.append("source", s));
    if (q.q) params.set("q", q.q);
    if (q.sentiment) params.set("sentiment", q.sentiment);
    if (q.aspect) params.set("aspect", q.aspect);
    if (q.sort) params.set("sort", q.sort);
    params.set("limit", String(q.limit ?? 25));
    params.set("offset", String(q.offset ?? 0));
    return request<RecordPage>(`/records?${params}`);
  },
  sentiment: (entityId: string, start: string, end: string, sources?: string[]) => {
    const params = new URLSearchParams({ start, end });
    sources?.forEach((s) => params.append("source", s));
    return request<SentimentBreakdown>(`/entities/${entityId}/sentiment?${params}`);
  },
  compare: (watchlistId: string, start: string, end: string, sources?: string[]) => {
    const params = new URLSearchParams({ watchlist_id: watchlistId, start, end });
    sources?.forEach((s) => params.append("source", s));
    return request<Comparison>(`/compare?${params}`);
  },
  forecasts: (watchlistId: string) => request<Forecast[]>(`/forecasts?watchlist_id=${watchlistId}`),
  createForecast: (entityId: string, horizonDays: number) =>
    request<Forecast>("/forecasts", { method: "POST", body: JSON.stringify({ entity_id: entityId, horizon_days: horizonDays }) }),
  evidence: (entityId: string, start: string, end: string) =>
    request<Evidence>(`/entities/${entityId}/evidence?start=${start}&end=${end}`),
  insights: (watchlistId: string) => request<InsightBatch>(`/insights?watchlist_id=${watchlistId}`),
  generateInsights: (watchlistId: string, useLlm = true) =>
    request<InsightBatch>("/insights/generate", { method: "POST", body: JSON.stringify({ watchlist_id: watchlistId, use_llm: useLlm }) }),
  exportUrl: (watchlistId: string, start: string, end: string, sources?: string[]) => {
    const params = new URLSearchParams({ watchlist_id: watchlistId, start, end });
    sources?.forEach((s) => params.append("source", s));
    return `/api/export/daily.csv?${params}`;
  },
  alerts: (watchlistId: string) => request<Alert[]>(`/alerts?watchlist_id=${watchlistId}`),
  alertEvents: (watchlistId: string, limit = 20) => request<AlertEvent[]>(`/alerts/events?watchlist_id=${watchlistId}&limit=${limit}`),
  createAlert: (entityId: string, rule: AlertRule, cooldownMinutes: number) =>
    request<Alert>("/alerts", { method: "POST", body: JSON.stringify({ entity_id: entityId, rule, cooldown_minutes: cooldownMinutes }) }),
  updateAlert: (id: string, patch: { active?: boolean }) =>
    request<Alert>(`/alerts/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  deleteAlert: (id: string) => request<void>(`/alerts/${id}`, { method: "DELETE" }),
  importCsv: (workspaceId: string, file: File, dataset: string, timezone: string) => {
    const form = new FormData();
    form.append("workspace_id", workspaceId);
    form.append("file", file);
    form.append("dataset", dataset);
    form.append("timezone", timezone);
    return request<CsvImportResult>("/imports/csv", { method: "POST", body: form });
  },
};
