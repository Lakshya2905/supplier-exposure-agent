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
  buffer_cover: 'How long stock lasts',
  portability: 'How hard to move supplier',
  concentration: 'Shared with other parts',
};

/** The unit each measure is counted in, spelled for a reader. */
export const DIMENSION_UNIT: Record<string, string> = {
  wait_out_days: 'days, quoted / worst case',
  resource_days: 'days',
  blast_radius: 'finished units a year',
  buffer_cover: 'days',
  portability: 'who owns the tooling',
  concentration: 'other exposed parts',
};

export const SURFACE_LABEL = {
  overview: 'Overview',
  exposure: 'Exposure',
  check: 'What to check',
  review: 'Review',
} as const;
