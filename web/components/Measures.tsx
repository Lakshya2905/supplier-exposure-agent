'use client';
/**
 * The six measures for one part, and the refusal to combine them.
 *
 * THIS IS THE DESIGN PROBLEM THAT MATTERS MOST. Six numbers with no hierarchy
 * read as an unfinished index unless the layout says otherwise, so:
 *
 *   EQUAL WIDTH, EQUAL WEIGHT. No measure is larger, bolder or first-among-
 *   equals. A grid with one emphasised cell is a ranking drawn.
 *
 *   EVERY UNIT PRINTED, under every figure. Three of these are in days and they
 *   are still three measures: waiting a disruption out, resourcing around it
 *   and covering it from stock are different questions that share a unit.
 *
 *   NO TOTAL ANYWHERE. There is no row at the foot and no place to put one.
 *
 *   WORDS WHERE AN INDEX WOULD GO. Underneath, what binds and what blocks,
 *   named by `src/binding.py` from terminal STATES rather than by comparing
 *   magnitudes. A "worst dimension" would be days measured against finished
 *   good units, which is the composite wearing a superlative.
 */
import { Tag } from '@carbon/react';
import { MeasureText } from './Absence';
import { DIMENSION_LABEL, DIMENSION_UNIT } from '@/lib/labels';
import { formatDays, formatNumber, isUnbounded } from '@/lib/measure';
import type { BindingSummary, DimensionScore, Measure } from '@/lib/types';

export const STANDING_COPY =
  'These are deliberately not combined into a single score. A part that takes ' +
  '26 weeks to replace is a different problem from one that just needs ' +
  're-approval, and an average hides which one is about to hurt you.';

function displayValue(score: DimensionScore): string | null {
  if (isUnbounded(score.value)) return 'unbounded';
  if (score.unit === 'categorical') {
    return typeof score.value === 'string' ? score.value : null;
  }
  if (score.unit === 'days') return formatDays(score.value);
  const text = formatNumber(score.value as Measure);
  return text === null ? null : Number(text).toLocaleString();
}

export function Measures({ scores, order }: {
  scores: Record<string, DimensionScore>; order: string[];
}) {
  return (
    <div className="sea-measures">
      {order.map((dimension) => {
        const score = scores[dimension];
        if (!score) return null;
        return (
          <div className="sea-measure" key={dimension}>
            <span className="sea-measure__name">
              {DIMENSION_LABEL[dimension] ?? dimension}
            </span>
            <span className="sea-measure__value">
              <MeasureText value={displayValue(score)}
                           completeness={score.completeness} />
            </span>
            <span className="sea-measure__unit">
              {DIMENSION_UNIT[dimension] ?? score.unit.replace(/_/g, ' ')}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function WhatBinds({ summary }: { summary: BindingSummary }) {
  return (
    <div className="sea-stack" style={{ marginTop: '1rem' }}>
      <div>
        <h4 className="sea-chart__title">What binds here</h4>
        {summary.binds.length === 0 ? (
          <p className="sea-section__note">
            Nothing about this part is at its worst state. That is the answer
            rather than a gap in one: the largest number on the row is not
            promoted to fill the space, because how much of the build stops and
            how long resourcing takes have no worst value until somebody sets a
            threshold.
          </p>
        ) : (
          <ul>
            {summary.binds.map((entry) => (
              <li key={entry.dimension} className="sea-section__note"
                  style={{ marginBottom: '0.5rem' }}>
                <strong>{DIMENSION_LABEL[entry.dimension] ?? entry.dimension}</strong>
                {' — '}{entry.sentence}
                {entry.autonomy === 'recommends' && (
                  <> <Tag type="warm-gray" size="sm">a person confirms this</Tag></>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
      {summary.blocks.length > 0 && (
        <div>
          <h4 className="sea-chart__title">What stops us saying more</h4>
          <ul>
            {summary.blocks.map((entry) => (
              <li key={entry.dimension} className="sea-section__note"
                  style={{ marginBottom: '0.5rem' }}>
                <strong>{DIMENSION_LABEL[entry.dimension] ?? entry.dimension}</strong>
                {' — '}{entry.sentence}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
