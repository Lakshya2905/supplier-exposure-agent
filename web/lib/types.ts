/** The shapes `src/api/encode.py` produces. Hand-written to match it. */
import type { Measure } from './measure';

export type { Measure };

export type Autonomy = 'executes' | 'recommends';

export type Completeness =
  | 'known' | 'upper_bound' | 'lower_bound'
  | 'cannot_tell' | 'no_recovery_path' | 'not_applicable';

export interface DimensionScore {
  part_number: string;
  dimension: string;
  value: Measure;
  unit: string;
  completeness: Completeness;
  autonomy: Autonomy;
  is_settled: boolean;
  reasons: string[];
  detail: Record<string, Measure>;
}

export interface Control {
  action: string;
  act_kind: string;
  subject: string;
  requires_reason: boolean;
  member_count: number;
  reason_codes: string[];
}

export interface Citation {
  field: string;
  value: string;
  source_file: string;
  row: number;
  system_of_record: string;
  retrieved_at: string;
  authority: string;
  transformation: string;
  locator: string;
}

export interface Evidence {
  part_number: string;
  supplier_rows: Array<Record<string, Measure>>;
  demand_rows: Array<Record<string, Measure>>;
  lead_time_used: Record<string, Measure> | null;
  notes: string[];
  transformations: Array<Record<string, Measure>>;
  contradictions: Array<Record<string, Measure>>;
  absences: Array<[string, string]>;
  sources_used: Array<{
    source_file: string; system_of_record: string;
    retrieved_at: string; rows: number[];
  }>;
}

export interface Row {
  entity: string;
  key: string;
  sentence: string;
  autonomy: Autonomy;
  controls: Control[];
  evidence: Evidence | null;
  detail: Record<string, Measure>;
  is_actionable: boolean;
}

export interface Group {
  name: string; label: string; rows: Row[];
  autonomy: Autonomy; order_label: string;
}

export interface CoverageNote {
  subject: string; count: number; sentence: string; kind: string;
}

export interface Surface {
  name: string;
  question: string;
  verb: string;
  row_entity: string;
  layers: Group[][];
  rows: Row[];
  coverage: { heading: string; notes: CoverageNote[]; is_empty: boolean } | null;
  notices: string[];
  evidence_by_part: Record<string, Evidence>;
}

export interface DimensionSeries {
  dimension: string;
  unit: string;
  /** Chart values. FLOATS, and a series rather than a measure: the exact
   *  figures are in `profiles`. Nothing quotable is read from here. */
  values: Array<number | [number, number]>;
  categories: Record<string, number>;
  unknown: number;
  unbounded: number;
}

export interface RegionRow {
  region: string; label: string; countries: string[];
  suppliers: number; parts: number; exposed_parts: number;
}

export interface RunRecord {
  id: string;
  created_at: string;
  dataset: string;
  data_dir: string;
  files: Array<{ name: string; sha256: string; bytes: number }>;
  counts: {
    parts_scored: number; dimension_results: number;
    executing: number; deferring: number; clusters_concentrated: number;
  };
}

export interface ScoreResult {
  run: RunRecord;
  overview: {
    tiles: Array<{ label: string; value: number; unit: string; of: string }>;
    dimension_series: DimensionSeries[];
    regions: RegionRow[];
    incidence: {
      parts: string[]; suppliers: string[];
      grid: number[][]; exposed_parts: number;
    };
    coverage_counts: Array<[string, number]>;
    group_sizes: Array<[string, number]>;
    field_sizes: Array<[string, number]>;
    cluster_sizes: Array<[string, number, string]>;
    region_labels: Record<string, string>;
  };
  verdicts: Record<string, string>;
  profiles: Record<string, Record<string, DimensionScore>>;
  surfaces: { exposure: Surface; what_to_check: Surface; review: Surface };
  clusters: Array<Record<string, Measure>>;
  unplaceable_parts: string[];
  extracts: Record<string, [string, string]>;
  dimensions: string[];
  /** Reviewer-owned magnitude thresholds, or null when nobody has set any.
   *  Null is the shipped state and is not a gap: the system can name the
   *  structural patterns and cannot say "long lead" until a person says what
   *  long means. */
  thresholds: { version?: string; thresholds?: Record<string, number> } | null;
  /** What binds and what blocks, per part. Computed in `src/binding.py` from
   *  terminal STATES, never by comparing magnitudes across units. */
  binding: Record<string, BindingSummary>;
}

export interface BindingEntry {
  dimension: string; sentence: string; autonomy: Autonomy;
}

export interface BindingSummary {
  binds: BindingEntry[];
  blocks: BindingEntry[];
  nothing_binds: boolean;
  no_terminal_state: Record<string, string>;
}

export interface DecisionEvent {
  event_id: number; at: string; status: string; sku_id: string;
  field: string; value: string; decided_by: string; reason_code: string;
  note: string; act_kind: string; member_count: number; kind: string;
  sentence: string;
}
