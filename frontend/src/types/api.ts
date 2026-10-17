export type EntityType = "brand" | "product" | "keyword" | "hashtag" | "competitor";

export interface Workspace {
  id: string;
  name: string;
  created_at: string;
}

export interface TrackedEntity {
  id: string;
  term: string;
  entity_type: EntityType;
  variants: string[];
  competitor_group: string | null;
  created_at: string;
}

export interface Watchlist {
  id: string;
  workspace_id: string;
  name: string;
  language: string;
  active: boolean;
  created_at: string;
  entities: TrackedEntity[];
}

export interface TrackedEntityCreate {
  term: string;
  entity_type: EntityType;
  variants?: string[];
  competitor_group?: string | null;
}

export type SourceStatus = "not_connected" | "never_run" | "running" | "ok" | "degraded" | "failed";

export interface IngestionRun {
  id: string;
  source: string;
  trigger: string;
  status: "queued" | "running" | "succeeded" | "partial" | "failed";
  started_at: string;
  ended_at: string | null;
  window_start: string | null;
  fetched_count: number | null;
  inserted_count: number | null;
  duplicate_count: number | null;
  rejected_count: number | null;
  matched_count: number | null;
  error_code: string | null;
  error_detail: string | null;
  coverage_json: Record<string, unknown> | null;
}

export interface Source {
  source: string;
  label: string;
  kind: "api" | "csv";
  enabled: boolean;
  policy_reviewed_at: string | null;
  policy_notes: string | null;
  status: SourceStatus;
  last_run: IngestionRun | null;
  last_success_at: string | null;
  record_count: number;
  notes: string[];
}

export interface CsvImportResult {
  run: IngestionRun;
  errors: { row: number; column: string | null; message: string }[];
  unknown_columns: string[];
}
