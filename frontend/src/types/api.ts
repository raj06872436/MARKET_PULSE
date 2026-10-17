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

export type Collection = "complete" | "incomplete" | "missing";

export interface SeriesPoint {
  date: string;
  collection: Collection;
  mentions: number | null;
  engagement: number | null;
  positive_share: number | null;
  neutral_share: number | null;
  negative_share: number | null;
  scored: number;
}

export interface EntitySeries {
  entity_id: string;
  term: string;
  entity_type: EntityType;
  points: SeriesPoint[];
}

export interface SeriesResponse {
  start: string;
  end: string;
  timezone: string;
  sources: string[];
  series: EntitySeries[];
}

export interface AspectSummary {
  aspect: string;
  mentions: number;
  positive: number;
  neutral: number;
  negative: number;
}

export interface EvidenceRecord {
  id: string;
  source: string;
  published_at: string;
  text: string | null;
  url: string | null;
  sentiment: string | null;
  confidence: number | null;
  flags: string[];
}

export interface Evidence {
  entity_id: string;
  start: string;
  end: string;
  mentions: number;
  scored: number;
  sentiment: Record<"positive" | "neutral" | "negative", number>;
  aspects: AspectSummary[];
  phrases: [string, number][];
  phrases_note: string;
  examples: EvidenceRecord[];
}

export interface TrendComponent {
  value: number | null;
  weight: number;
  reason?: string;
  [key: string]: unknown;
}

export interface TrendDetails {
  components: Record<"mention_growth" | "engagement_growth" | "sentiment_shift" | "persistence", TrendComponent>;
  confidence: "high" | "medium" | "low";
  coverage: number;
  window: { start: string; end: string; previous_start: string; previous_end: string };
  version: string;
}

export interface TrendCard {
  entity_id: string;
  term: string;
  entity_type: EntityType;
  competitor_group: string | null;
  date: string | null;
  score: number | null;
  explanation_code: string | null;
  details: TrendDetails | null;
  sparkline: SeriesPoint[];
  evidence: Evidence | null;
}
