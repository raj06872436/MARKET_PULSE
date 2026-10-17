export type EntityType = "brand" | "product" | "keyword" | "hashtag" | "competitor";

export interface User {
  id: string;
  email: string;
  role: "admin" | "member";
  created_at: string;
}

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

export interface DataCheck {
  name: string;
  passed: boolean;
  detail: string;
}

export interface MethodScore {
  name: string;
  label: string;
  kind: "baseline" | "candidate";
  mae: number | null;
  rmse: number | null;
  wape: number | null;
  n: number;
  mae_by_horizon: (number | null)[];
}

export interface ForecastPoint {
  date: string;
  predicted: number;
  lower: number | null;
  upper: number | null;
  actual: number | null;
}

export interface Forecast {
  id: string;
  entity_id: string;
  term: string;
  status: "ready" | "insufficient_data" | "failed";
  method: string | null;
  method_label: string | null;
  model_version: string;
  horizon_days: number;
  training_start: string | null;
  training_end: string | null;
  created_at: string;
  checks: DataCheck[];
  interval_level: number;
  interval_coverage: number | null;
  candidate_beats_baseline: boolean | null;
  backtest: { origins: string[]; horizon_days: number; methods: MethodScore[] } | null;
  history: { date: string; mentions: number | null }[];
  points: ForecastPoint[];
}

export interface DataRange {
  first: string | null;
  last: string | null;
  sources: string[];
}

export type SentimentLabel = "positive" | "neutral" | "negative";

export interface RecordRow {
  id: string;
  source: string;
  published_at: string;
  text: string | null;
  url: string | null;
  engagement: number | null;
  sentiment: SentimentLabel | null;
  confidence: number | null;
  flags: string[];
  aspects: { aspect: string; sentiment: SentimentLabel }[];
  terms: string[];
}

export interface RecordPage {
  total: number;
  limit: number;
  offset: number;
  items: RecordRow[];
}

export interface RecordQuery {
  watchlistId: string;
  start: string;
  end: string;
  entityIds?: string[];
  sources?: string[];
  q?: string;
  sentiment?: SentimentLabel | "unscored";
  aspect?: string;
  sort?: "newest" | "oldest" | "engagement";
  limit?: number;
  offset?: number;
}

export interface SentimentBreakdown {
  entity_id: string;
  term: string;
  start: string;
  end: string;
  sources: string[];
  mentions: number;
  scored: number;
  counts: Record<SentimentLabel, number>;
  flagged: Record<string, number>;
  aspects: AspectSummary[];
  positive_phrases: [string, number][];
  negative_phrases: [string, number][];
  positive_examples: EvidenceRecord[];
  negative_examples: EvidenceRecord[];
}

export interface Scorecard {
  entity_id: string;
  term: string;
  entity_type: EntityType;
  competitor_group: string | null;
  mentions: number;
  share_of_voice: number | null;
  collected_days: number;
  engagement_per_post: number | null;
  engagement_records: number;
  scored: number;
  net_sentiment: number | null;
  positive_share: number | null;
  negative_share: number | null;
  aspects: { aspect: string; mentions: number; negative_share: number }[];
}

export interface Comparison {
  start: string;
  end: string;
  days: number;
  sources: string[];
  scorecards: Scorecard[];
  aspect_gaps: {
    aspect: string;
    entity_id: string;
    term: string;
    mentions: number;
    negative_share: number;
    others_negative_share: number;
    difference: number;
  }[];
}

export interface InsightFact {
  id: string;
  label: string;
  value: number | string | null;
  unit: "" | "percent" | "score" | "posts" | "days";
}

export interface InsightExample {
  id: string;
  entity_alias: string;
  published_at: string;
  sentiment: SentimentLabel | null;
  text: string;
  url: string | null;
}

export interface Insight {
  id: string;
  watchlist_id: string | null;
  entity_id: string | null;
  period_start: string;
  period_end: string;
  observation: string;
  interpretation: string | null;
  caveat: string | null;
  suggested_action: string | null;
  evidence: { facts: InsightFact[]; examples: InsightExample[]; comparison?: { start: string; end: string } };
  generator: "llm" | "template";
  model_version: string;
  generated_at: string;
}

export interface InsightBatch {
  generator: "llm" | "template";
  llm_status: string;
  llm_available: boolean;
  rejected: { observation: string; problems: string[] }[];
  insights: Insight[];
}

export type AlertMetric = "daily_mentions" | "weekly_change" | "negative_share" | "trend_score";

export interface AlertRule {
  metric: AlertMetric;
  threshold: number;
  min_posts?: number;
}

export interface Alert {
  id: string;
  entity_id: string;
  term: string;
  rule: AlertRule;
  cooldown_minutes: number;
  active: boolean;
  last_triggered_at: string | null;
  created_at: string;
}

export interface AlertEvent {
  id: string;
  alert_id: string;
  entity_id: string;
  term: string;
  triggered_at: string;
  data_date: string;
  value: number;
  threshold: number;
  message: string;
}
