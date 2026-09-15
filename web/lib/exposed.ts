/**
 * One row per exposed part, most specific pattern first.
 *
 * THIS WALK EXISTS BECAUSE A PART APPEARS IN EVERY GROUP IT MATCHES, which is
 * the lattice working as designed: a part matching "one supplier,
 * supplier-owned tooling, shared with other parts" also matches "one supplier,
 * supplier-owned tooling", because dominance is strict subset inclusion of
 * conditions. Walking the layers naively yields 36 rows for 21 parts.
 *
 * IT IS SHARED BECAUSE THE SECOND COPY GOT IT WRONG. The exposure table
 * de-duplicated; the printed run summary re-walked the layers without doing so,
 * and listed fourteen parts twice in the PDF with identical sentences, under
 * duplicate React keys. Two implementations of "which parts are exposed" is one
 * too many, and the one nobody looks at is the one that drifts.
 *
 * FIRST WINS, and that is not arbitrary. The surface returns groups in
 * dominance-layer order, so the first match a part appears under CONTAINS every
 * later one: telling a reader the broader pattern as well adds no condition they
 * have not already been told. The rest are kept on `archetypes` so "contained"
 * stays something they can check rather than something they must accept.
 */
import type { Row, Surface } from './types';

export interface ExposedRow extends Row {
  /** Every pattern this part matched, most specific first. */
  archetypes: string[];
}

export function exposedRows(surface: Surface): ExposedRow[] {
  const order: ExposedRow[] = [];
  const seen = new Map<string, ExposedRow>();
  for (const layer of surface.layers) {
    for (const group of layer) {
      for (const row of group.rows) {
        const already = seen.get(row.key);
        if (already) {
          already.archetypes.push(group.label);
          continue;
        }
        const entry: ExposedRow = { ...row, archetypes: [group.label] };
        seen.set(row.key, entry);
        order.push(entry);
      }
    }
  }
  return order;
}
