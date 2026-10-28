/**
 * One row per measure, for the table that replaced the Overview charts.
 *
 * THE ARITHMETIC IS SHARED; THE MARKUP IS NOT. Screen and print draw different
 * tables because they are different media, but "how many parts have a figure"
 * is one question and must have one answer. It was computed twice before -- in
 * `SeriesPanel` on the Overview and again in `RunSummary` for the printed page
 * -- and `lib/exposed.ts` carries the note about what happened the last time
 * this repository derived the same count in two places.
 *
 * UNBOUNDED COUNTS AS A FIGURE, which is a claim worth stating rather than
 * burying in an addition. Stock with nothing consuming it lasts indefinitely:
 * that is an answer, not an absence, and `scoring.buffer_cover` returns it as
 * `completeness=known`. The charts had to name it separately because a
 * histogram cannot draw infinity; a table has no such problem, so the figure
 * goes where it belongs and `unbounded` is carried for any caller that wants to
 * say how many of them there are.
 */
import { DIMENSION_LABEL, DIMENSION_UNIT } from './labels';
import type { DimensionSeries } from './types';

export interface MeasureRow {
  dimension: string;
  label: string;
  unit: string;
  /** Parts this measure settled, including the unbounded ones. */
  assessed: number;
  unknown: number;
  unbounded: number;
}

export function measureRows(series: DimensionSeries[]): MeasureRow[] {
  return series.map((entry) => ({
    dimension: entry.dimension,
    label: DIMENSION_LABEL[entry.dimension] ?? entry.dimension,
    unit: DIMENSION_UNIT[entry.dimension] ?? entry.unit.replace(/_/g, ' '),
    assessed: entry.values.length
      + Object.values(entry.categories).reduce((a, b) => a + b, 0)
      + entry.unbounded,
    unknown: entry.unknown,
    unbounded: entry.unbounded,
  }));
}
