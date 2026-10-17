import type {
  CsvImportResult,
  Evidence,
  SeriesResponse,
  TrendCard,
  IngestionRun,
  Source,
  TrackedEntity,
  TrackedEntityCreate,
  Watchlist,
  Workspace,
} from "../types/api";

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
  const response = await fetch(`/api${path}`, {
    headers: isForm ? undefined : { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail =
      typeof body?.detail === "string"
        ? body.detail
        : Array.isArray(body?.detail)
          ? body.detail.map((d: { msg?: string }) => d.msg).join("; ")
          : response.statusText;
    throw new ApiError(response.status, detail);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export const api = {
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
  evidence: (entityId: string, start: string, end: string) =>
    request<Evidence>(`/entities/${entityId}/evidence?start=${start}&end=${end}`),
  importCsv: (file: File, dataset: string, timezone: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("dataset", dataset);
    form.append("timezone", timezone);
    return request<CsvImportResult>("/imports/csv", { method: "POST", body: form });
  },
};
