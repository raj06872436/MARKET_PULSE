import type { TrackedEntity, TrackedEntityCreate, Watchlist, Workspace } from "../types/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : response.statusText;
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
};
