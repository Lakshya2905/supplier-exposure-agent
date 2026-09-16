/**
 * What a person reads, for a key the system stores.
 *
 * INTERNAL KEYS ARE NEVER REWRITTEN, only presented. `south_asia` is the
 * identity of a cluster and every decision recorded against it uses that
 * string; changing it to make a screen read well would fork the audit trail
 * from the thing it audits. So keys go over the wire untouched and this file
 * is the last step before paint.
 *
 * THE CASING BUG THIS CLOSES. The Streamlit surface shows `north_america`,
 * `SOUTH_ASIA` and `south_asia` in three places, which reads as three different
 * things. Region display names are served by the API from one map in
 * `interface.dashboard` rather than being reproduced here, because a second
 * copy is how they drift apart again; `titleCase` is the fallback for a key
 * that map has never heard of, and it is deliberately a fallback rather than
 * the mechanism.
 */

/** The product name, in ONE place.
 *
 * It was spelled in the page metadata and again in the header wordmark, which
 * is two copies of one name. That is the shape of a defect this repository has
 * already had twice: the nav label and the page title were two copies, and
 * renaming one timed out every rendered-page check. The wordmark splits the
 * name for its weight break and therefore needs the halves, so both are here
 * and the whole is derived rather than retyped.
 */
/** The run-out comparison, in a planner's words.
 *
 * THE TAG TYPE IS NOMINAL, NOT A RAMP. `too_close_to_call` is deliberately off
 * the red-green axis rather than sitting between them: it is not "medium
 * risk", it is a different KIND of statement -- the data settles neither way.
 * Putting it on the ramp would invite a reader to average three categories that
 * do not average.
 */
export const RUN_OUT = {
  runs_out_first: { label: 'Runs out first', tag: 'red' },
  outlasts_it: { label: 'Stock outlasts it', tag: 'green' },
  too_close_to_call: { label: 'Too close to call', tag: 'purple' },
  cannot_say: { label: 'Not enough data to say', tag: 'warm-gray' },
  does_not_apply: { label: 'Does not apply here', tag: 'cool-gray' },
  no_supplier_at_all: { label: 'No supplier to order from', tag: 'red' },
} as const;

/** What the loss of a supplier would do to a part, in a planner's words.
 *
 * NOMINAL, SO NO HUE. These are five outcomes with a stated worst-first
 * sequence, not a scale, and DESIGN.md retired hue from nominal sets. The
 * ORDER carries the severity and the words carry the meaning. */
/** CHIP LENGTH, because that is where it is rendered. The longer form said
 *  "Stops. Nobody left who could take the order" and Carbon truncated it to
 *  "Stops. Nobody left who could tak...". The sentence beside the chip already
 *  names how many suppliers remain, so nothing was lost by cutting it. */
export const OUTCOME = {
  stops: 'Stops',
  sole_sourced: 'Down to one source',
  unsettled: 'Cannot be settled',
  still_multi: 'Other sources remain',
  does_not_apply: 'Made in-house',
} as const;

/** The same five outcomes as a clause, for the one-line summary.
 *
 * A SECOND FORM RATHER THAN THE FIRST LOWERCASED. `OUTCOME.stops` is a
 * sentence and lowercasing it produced "2 stops. nobody left who could take
 * the order", which reads as a typo. A label that has to be reshaped to fit a
 * sentence is two labels. */
export const OUTCOME_CLAUSE = {
  stops: 'would stop',
  sole_sourced: 'would drop to one source',
  unsettled: 'could not be settled',
  still_multi: 'would still have other sources',
  does_not_apply: 'are made in-house',
} as const;

export const PRODUCT_LEAD = 'Supplier Exposure';
export const PRODUCT_TAIL = 'Agent';
export const PRODUCT_NAME = `${PRODUCT_LEAD} ${PRODUCT_TAIL}`;

/** Underscores out, first letters up. For keys nothing authoritative names. */
export function titleCase(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
    .replace(/(^|\s)(\w)/g, (_m, lead, letter) => lead + letter.toUpperCase());
}

/** A display name from the API's map, falling back to title case. */
export function labelFor(key: string, served: Record<string, string> = {}) {
  return served[key] ?? titleCase(key);
}

/** A dimension's name, in the words used across the app. */
// SHORT, AND IN THE SAME VOCABULARY AS THE SENTENCES. A tile heading cannot
// carry "how long until parts flow again from this supplier", so these are the
// short forms; what they must not be is a SECOND vocabulary, where a heading
// says "portability" and the sentence under it says "how hard it is to move".
export const DIMENSION_LABEL: Record<string, string> = {
  wait_out_days: 'Wait for this supplier',
  resource_days: 'Get a new supplier approved',
  blast_radius: 'How much of the build stops',
  committed_at_risk: 'Promised orders missed',
  buffer_cover: 'How long stock lasts',
  portability: 'How hard to move supplier',
  concentration: 'Shared with other parts',
};

/** The unit each measure is counted in, spelled for a reader. */
export const DIMENSION_UNIT: Record<string, string> = {
  wait_out_days: 'days, quoted / worst case',
  resource_days: 'days',
  blast_radius: 'finished units a year',
  committed_at_risk: 'promised units',
  buffer_cover: 'days',
  portability: 'who owns the tooling',
  concentration: 'other exposed parts',
};

/** What each kind of change is, in the words a planner would use.
 *
 *  KEYED BY KIND, NEVER DERIVED FROM A SIGN. "Became unknown" has no sign, and a
 *  UI that inferred direction from a delta would have nowhere to put it. */
export const CHANGE_LABEL: Record<string, string> = {
  newly_exposed: 'Now down to one supplier',
  no_longer_exposed: 'No longer down to one supplier',
  verdict_changed: 'Supplier situation changed',
  measure_moved: 'A figure moved',
  became_unknown: 'We can no longer say',
  became_known: 'We can now say',
  entered_scope: 'Newly assessed',
  left_scope: 'Not assessed this time',
  cluster_grew: 'More parts share this',
  cluster_shrank: 'Fewer parts share this',
  cluster_appeared: 'Parts started sharing this',
};

/** Kinds that are about the SCOPE rather than about the world.
 *
 *  A part that was not assessed did not get better, and separating these is
 *  what stops somebody improving the numbers by scoping harder. */
export const SCOPE_KINDS = ['entered_scope', 'left_scope'];

export const SURFACE_LABEL = {
  overview: 'Overview',
  exposure: 'Exposure',
  check: 'What to check',
  review: 'Review',
} as const;
