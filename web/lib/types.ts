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

/** One country, filled as a stand-in for the region it was assigned to. The
 *  assignment is a DRAWING CONVENTION, not a claim about where a supplier is. */
export interface MapRow {
  country: string; name: string;
  region: string; region_label: string;
  suppliers: number; parts: number; exposed_parts: number;
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
    map_rows: MapRow[];
    incidence: {
      parts: string[]; suppliers: string[];
      grid: number[][]; exposed_parts: number;
    };
    coverage_counts: Array<[string, number]>;
    group_sizes: Array<[string, number]>;
    field_sizes: Array<[string, number]>;
    cluster_sizes: Array<[string, number, string]>;
    region_labels: Record<string, string>;
    /** Verdict codes in plain words, from the renderer's own map. */
    verdict_labels: Record<string, string>;
  };
  verdicts: Record<string, string>;
  profiles: Record<string, Record<string, DimensionScore>>;
  surfaces: { exposure: Surface; what_to_check: Surface; review: Surface };
  clusters: Array<Record<string, Measure>>;
  unplaceable_parts: string[];
  extracts: Record<string, [string, string]>;
  dimensions: string[];
  /** What this run assessed and what it did not. Present even when nothing was
   *  left out, because "we looked at everything" is a claim worth seeing made. */
  scope: Scope;
  /** Reviewer-owned magnitude thresholds, or null when nobody has set any.
   *  Null is the shipped state and is not a gap: the system can name the
   *  structural patterns and cannot say "long lead" until a person says what
   *  long means. */
  thresholds: { version?: string; thresholds?: Record<string, number> } | null;
  /** What binds and what blocks, per part. Computed in `src/binding.py` from
   *  terminal STATES, never by comparing magnitudes across units. */
  binding: Record<string, BindingSummary>;
  /** Does stock outlast the next delivery? An ORDERING, never a difference.
   *
   *  A SIBLING OF `profiles`, NEVER A MEMBER OF IT. Everything in there is a
   *  scored dimension; this is a comparison of two of them. It carries no unit
   *  and no magnitude, because a margin in days is the subtraction the README
   *  declines. See `src/runout.py`. */
  run_out: Record<string, RunOut>;
}

export interface RunOut {
  part_number: string;
  outcome: 'runs_out_first' | 'outlasts_it' | 'too_close_to_call'
    | 'cannot_say' | 'does_not_apply' | 'no_supplier_at_all';
  reasons: string[];
  /** The two figures compared, carried as evidence. Nothing derived from both. */
  cover_days: Measure | null;
  quoted_days: number | null;
  p95_days: number | null;
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

export interface Scope {
  labels: string[];
  included: string[];
  parts_in_scope: string[];
  parts_excluded: string[];
  counts: Record<string, number>;
  is_scoped: boolean;
  excluded_labels: string[];
  sentence: string;
}

/** One thing that is different between two runs.
 *
 *  `worsened` IS THREE-VALUED and the third value is the point: a measure that
 *  stopped being answerable has not worsened and has not improved, and a UI
 *  that renders `!worsened` as "improved" reintroduces at the last moment the
 *  collapse both runs avoided. */
export interface Change {
  kind: string;
  subject: string;
  dimension: string;
  before: Measure;
  after: Measure;
  worsened: boolean | null;
  detail: Record<string, Measure>;
}

export interface Comparison {
  before: RunRecord & { provenance: Record<string, Measure> };
  after: RunRecord & { provenance: Record<string, Measure> };
  changes: Change[];
  counts: Record<string, number>;
  worsened: number;
  unjudged: number;
}

export interface DecisionEvent {
  event_id: number; at: string; status: string; sku_id: string;
  field: string; value: string; decided_by: string; reason_code: string;
  note: string; act_kind: string; member_count: number; kind: string;
  sentence: string;
}
