/**
 * tipos/api.ts — DTOs que espejan el contrato REAL de la API (API.md §0.1/§0.2).
 *
 * Reglas:
 * - error.code es STRING ("DATA_ERROR", "INTERNAL_ERROR"...) NUNCA number.
 * - NetworkKind usa los valores del núcleo (bibliographic_coupling, etc.), NO los del mock.
 * - Paper expone listas crudas (authors_raw, keywords_id), NO objetos Author/ORCID.
 * - NetworkData NO tiene modularity ni id de red persistido.
 * - RoundDiff tiene mutated_hubs como unknown[] (diferido, hoy []).
 */

// ---------------------------------------------------------------------------
// Envelope (API.md §0)
// ---------------------------------------------------------------------------

export interface EnvelopeError {
  /** code es STRING: "DATA_ERROR" | "INTERNAL_ERROR" | "USAGE_ERROR" | etc. */
  code: string;
  message: string;
}

export interface Envelope<T> {
  schema: "1";
  ok: boolean;
  command: string;
  exit_code: number;
  data: T;
  warnings: string[];
  error: EnvelopeError | null;
}

// ---------------------------------------------------------------------------
// Enums del dominio
// ---------------------------------------------------------------------------

export type CurationStatus = "candidate" | "accepted" | "rejected";

/** Valores del núcleo (NetworkKind del servidor). */
export type NetworkKind =
  | "bibliographic_coupling"
  | "cocitation"
  | "author_collab"
  | "institution_collab"
  | "keyword_cooccurrence";

// ---------------------------------------------------------------------------
// WorkspaceState — GET /api/workspace (API.md §0.1 get_workspace)
// ---------------------------------------------------------------------------

export interface WorkspaceState {
  name: string;
  root: string;
  created_at: string;
  bib2graph_version: string;
  source: string | null;
  loop_state: string | null;
  round: number;
  total_papers: number;
  counts_by_status: Record<string, number>;
  transitions_available: string[];
  curation_available: string[];
  networks_cache_stale: boolean;
}

// ---------------------------------------------------------------------------
// RoundEntry — GET /api/rounds (API.md §0.1 list_rounds)
// ---------------------------------------------------------------------------

export interface RoundEntry {
  id: string;
  corpus_hash?: string;
  created_at?: string;
  total_papers: number;
  schema_version?: string;
  /** Solo en id="live" */
  round?: number;
  /** Solo en id="live" */
  loop_state?: string | null;
}

export interface RoundsData {
  rounds: RoundEntry[];
}

// ---------------------------------------------------------------------------
// Paper — GET /api/paper/{id} (API.md §0.1 get_paper)
// ---------------------------------------------------------------------------

export interface Paper {
  id: string;
  openalex_id: string | null;
  doi: string | null;
  title: string;
  year: number | null;
  abstract: string | null;
  is_seed: boolean;
  curation_status: CurationStatus;
  /** Listas crudas — NO objetos Author/ORCID */
  authors_raw: string[];
  authors_id: string[];
  keywords_id: string[];
  references_id: string[];
  cited_by_id: string[];
  provenance: unknown[];
}

// ---------------------------------------------------------------------------
// Scent — GET /api/paper/{id}/scent (API.md §0.1 get_scent)
// ---------------------------------------------------------------------------

export interface ScentNeighbor {
  paper_id: string;
  /** Puede ser null si el server no resolvió el título del vecino (reads.py). */
  title: string | null;
  weight?: number;
}

export interface Scent {
  paper_id: string;
  /** Score escalar: nº de corpus-papers con >=1 referencia compartida */
  score: number;
  coupling: ScentNeighbor[];
  references: ScentNeighbor[];
  cited_by: ScentNeighbor[];
}

// ---------------------------------------------------------------------------
// NetworkData — GET /api/network/{kind} (API.md §0.1 get_network)
// ---------------------------------------------------------------------------

export interface NetworkNode {
  id: string;
  label: string;
  degree_centrality: number;
  community?: number;
  year?: number;
  is_seed?: boolean;
  curation_status?: CurationStatus;
}

export interface NetworkEdge {
  source: string;
  target: string;
  weight: number;
}

export interface NetworkMetrics {
  n_nodes: number;
  n_edges: number;
  density: number;
  num_components: number;
  avg_clustering: number;
  n_communities: number;
}

export interface NetworkData {
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  metrics: NetworkMetrics;
}

// ---------------------------------------------------------------------------
// RoundDiff — GET /api/compare?a=&b= (API.md §0.1 compare_rounds)
// ---------------------------------------------------------------------------

export interface MetricChange {
  metric: string;
  before: number;
  after: number;
}

export interface RoundDiff {
  round_a: string;
  round_b: string;
  added_paper_ids: string[];
  removed_paper_ids: string[];
  /** Diferido (B-G2-3): hoy siempre [] */
  mutated_hubs: unknown[];
  metrics_change: MetricChange[];
}

// ---------------------------------------------------------------------------
// CurateResult — POST /api/paper/{id}/curate (API.md §0.2)
// ---------------------------------------------------------------------------

export interface CurateRequest {
  decision: "accepted" | "rejected";
}

export interface CurateResult {
  accepted_count?: number;
  rejected_count?: number;
  ids: string[];
}
