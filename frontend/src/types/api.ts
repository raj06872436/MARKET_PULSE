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
