'use client';
/**
 * Every chart in the application, so the rules hold in one place.
 *
 * ONE PALETTE, ONE GRID, SET HERE AND NOWHERE ELSE. The Streamlit surface ran
 * olive, maroon, purple and teal with no system behind it, which reads as four
 * unrelated screens. Carbon Charts supplies the categorical palette and the
 * grid; what this file adds is the rules Carbon cannot know:
 *
 *   NEVER TWO MEASURES ON ONE AXIS. There is no unit in which days and
 *   finished-good units are the same quantity, so a chart drawing both would be
 *   the composite the arithmetic refuses, assembled by eye instead.
 *
 *   EVERY AXIS CARRIES ITS UNIT, in the title, always.
 *
 *   ZERO BASELINE ON EVERY BAR. A truncated bar chart exaggerates difference,
 *   which is the visual version of a threshold nobody set.
 *
 *   AN EMPTY SERIES IS NOT AN EMPTY CHART. A histogram of nothing still draws
 *   an axis from zero, and an axis under a full heading reads as "everything
 *   scored low" rather than "no part has a figure". Those are different claims
 *   and one of them is false, so `ChartOrAbsence` refuses to draw the axis.
 */
import { SimpleBarChart, HistogramChart } from '@carbon/charts-react';
import { ScaleTypes } from '@carbon/charts';
import '@carbon/charts/styles.css';

const BASE = {
  axes: {
    left: { mapsTo: 'value', includeZero: true },
    bottom: { mapsTo: 'group', scaleType: ScaleTypes.LABELS },
  },
  height: '14rem',
  toolbar: { enabled: false },
  legend: { enabled: false },
  grid: { x: { enabled: false }, y: { enabled: true } },
  theme: 'g10' as const,
};

export interface Countable { label: string; value: number }

export function CountBar({ data, unit, title }: {
  data: Countable[]; unit: string; title?: string;
}) {
  return (
    <SimpleBarChart
      data={data.map((entry) => ({ group: entry.label, value: entry.value }))}
      options={{
        ...BASE,
        title,
        axes: {
          left: { mapsTo: 'value', title: unit, includeZero: true },
          bottom: { mapsTo: 'group', scaleType: ScaleTypes.LABELS, title: '' },
        },
      }}
    />
  );
}

export function Distribution({ values, unit }: {
  values: number[]; unit: string;
}) {
  return (
    <HistogramChart
      data={values.map((value) => ({ group: unit, value }))}
      options={{
        ...BASE,
        axes: {
          bottom: { mapsTo: 'value', title: unit, bins: 20,
                    scaleType: ScaleTypes.LINEAR },
          left: { mapsTo: 'value', title: 'parts', scaleType: ScaleTypes.LINEAR,
                  stacked: true, binned: true, includeZero: true },
        },
      }}
    />
  );
}

/**
 * A chart, or a stated absence at the same footprint.
 *
 * The absence renders at full text weight and the same height as a chart,
 * because a measure nothing has established is a finding and not a blank.
 */
export function ChartOrAbsence({ assessed, unknown, children }: {
  assessed: number; unknown: number; children: React.ReactNode;
}) {
  if (assessed > 0) return <>{children}</>;
  return (
    <div className="sea-chart__absent">
      <span>
        No part has an established figure for this measure.{' '}
        {unknown.toLocaleString()} results say so rather than reporting a number
        nobody supplied.
      </span>
    </div>
  );
}
