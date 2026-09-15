/**
 * Reading the wire format, and the one place this frontend rounds.
 *
 * THE PAYLOAD IS TAGGED BECAUSE THE DISTINCTIONS ARE REAL. `src/api/encode.py`
 * carries four of them across the network and this file is where they either
 * reach the screen or get flattened one import from the end:
 *
 *   null is NOT zero. A blank on-hand record and a counted zero are different
 *   findings, one a gap in a spreadsheet and the other the worst cover in the
 *   dataset. `value ?? 0` anywhere below fuses them permanently, and it is the
 *   idiom every TypeScript codebase reaches for.
 *
 *   an exact rational is NOT a float until it is painted. Cover is 73/2, and
 *   it crosses the wire as its numerator and denominator precisely so that
 *   rounding happens HERE, at the last possible moment, and nowhere earlier.
 *
 *   unbounded is an ANSWER. Cover with nothing consuming it is settled. It must
 *   never join the unknown pile, and it has no numeric position, so it is never
 *   charted as a very large number.
 *
 *   a pair is NOT a rational. `wait_out_days` is [quoted, p95]; both are two
 *   numbers and only the tag tells them apart.
 *
 * ABSENCE IS NEVER RENDERED AS ZERO, BLANK OR A DASH. `DESIGN.md` states it and
 * this file is where a UI usually breaks it, because a table cell wants a
 * string and `""` is always to hand. Every formatter here returns `null` for an
 * absent value and the components render an absence Tag at full weight instead.
 */

export type Exact = { type: 'exact'; numerator: number; denominator: number };
export type Unbounded = { type: 'unbounded' };
export type Measure =
  | number | string | boolean | null | Exact | Unbounded | Measure[];

export const isExact = (v: Measure): v is Exact =>
  typeof v === 'object' && v !== null && !Array.isArray(v) && v.type === 'exact';

export const isUnbounded = (v: Measure): v is Unbounded =>
  typeof v === 'object' && v !== null && !Array.isArray(v) &&
  v.type === 'unbounded';

export const isPair = (v: Measure): v is [Measure, Measure] =>
  Array.isArray(v) && v.length === 2;

/**
 * A measure as a number, or null when it does not have one.
 *
 * Returns null for unbounded ON PURPOSE. Unbounded cover is an answer with no
 * numeric position, and the obvious alternatives are both lies: Infinity plots
 * off the end of every axis and Number.MAX_VALUE is a very large measurement.
 * Callers charting these must carry the unbounded count beside the series,
 * which is exactly what `DimensionSeries` already does.
 */
export function toNumber(value: Measure): number | null {
  if (value === null || typeof value === 'boolean') return null;
  if (typeof value === 'number') return value;
  if (isExact(value)) return value.numerator / value.denominator;
  return null;
}

/** One decimal, or none when the value is whole. The only rounding here. */
export function formatNumber(value: Measure): string | null {
  const n = toNumber(value);
  if (n === null) return null;
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

export function formatDays(value: Measure): string | null {
  if (isUnbounded(value)) return 'unbounded';
  if (isPair(value)) {
    const [quoted, p95] = value.map(formatNumber);
    return quoted === null ? null : `${quoted} / ${p95}`;
  }
  const text = formatNumber(value);
  return text === null ? null : `${text} days`;
}

/**
 * Whether a stated bound actually carries information.
 *
 * ZERO IS THE TRIVIAL LOWER BOUND OF ANY NON-NEGATIVE QUANTITY, so "at least 0
 * units a year" is a true statement that says nothing while looking like a
 * measurement. `src/governance/render.py` carries the same repair for the
 * sentence form, under `_blocked_volume_absent`, and its comment records that
 * the defect shipped once: the bound prefix promised a figure and delivered
 * none, forty characters from a correct treatment of the same problem.
 *
 * This is the general rule rather than the blast-radius special case, because
 * it is true of every lower bound and not of that one measure.
 */
export function boundIsTrivial(value: Measure, completeness: string): boolean {
  return completeness === 'lower_bound' && toNumber(value) === 0;
}

export function formatUnits(value: Measure, unit: string): string | null {
  const text = formatNumber(value);
  if (text === null) return null;
  return `${Number(text).toLocaleString()} ${unit.replace(/_/g, ' ')}`;
}
