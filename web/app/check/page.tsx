'use client';
/**
 * What to check: which single fetch settles the most. The row is a FIELD.
 *
 * THE ROW IS THE FIELD AND NOT THE PART, and that is the whole design. Twenty-
 * six parts missing an on-hand count is ONE trip to one system, not twenty-six
 * pieces of work, and a list of parts would present it as twenty-six.
 *
 * THIS PAGE IS LEGITIMATELY A RANKING, unlike every other. It asks which one
 * fetch settles the most memberships, and the answer is a count of parts in one
 * unit. Nothing here compares two different things.
 *
 * NOTHING IS IMPUTED. The queue ranks by whether a missing field could change
 * an outcome, evaluated with the field unknown, never by a plausible value for
 * it. A list ordered by a guessed value is a forecast wearing a work queue's
 * clothes.
 */
import { useState } from 'react';
import {
  Button, CodeSnippet, StructuredListBody, StructuredListCell,
  StructuredListHead, StructuredListRow, StructuredListWrapper, Tag,
} from '@carbon/react';
import { useRun } from '@/components/RunProvider';
import { CountBar } from '@/components/Charts';
import { Empty, Failed, Loading } from '@/components/States';
import { downloadCsv } from '@/lib/csv';
import type { Measure } from '@/lib/measure';

const FIELD_LABEL: Record<string, string> = {
  on_hand_units: 'an on-hand count',
  tooling_owner: 'a tooling owner',
  verdict: 'a confirmed supplier list',
  concentration: 'a resolved supplier name merge',
  wait_out_days: 'a lead time record',
  resource_days: 'a timed resourcing chain',
};

function partsOf(detail: Record<string, Measure>): string[] {
  const parts = detail.parts;
  return Array.isArray(parts) ? parts.map(String) : [];
}

export default function WhatToCheck() {
  const { result, loading, error, reload } = useRun();
  const [expanded, setExpanded] = useState<string | null>(null);

  if (loading && !result) return <Loading label="Scoring the dataset." />;
  if (!result) return <Failed error={error} onRetry={reload} />;

  const surface = result.surfaces.what_to_check;

  return (
    <section className="sea-section">
      <h2 className="sea-section__heading">What to check</h2>
      <p className="sea-section__note">
        Each row is one fact, not one part. Fetching it once settles every part
        listed against it, which is why the row is the field: twenty-six parts
        missing the same number is one trip to one system. Ordered by how many
        parts one fetch would settle, which is the one ranking in this tool that
        compares like with like.
      </p>
      <p className="sea-section__note">
        Nothing here guesses what the missing value is. A part appears because
        the outcome genuinely turns on the field, evaluated with it unknown.
      </p>

      {surface.rows.length === 0 ? (
        <Empty title="Nothing is waiting on a missing field">
          Every part in this run either matched a pattern or was excluded by a
          fact already on file. No fetch would change an outcome.
        </Empty>
      ) : (
        <>
          <div className="sea-chart" style={{ marginBottom: '1.5rem' }}>
            <div className="sea-chart__title">Parts one fetch would settle</div>
            <div className="sea-chart__unit">parts</div>
            <CountBar
              unit="parts"
              data={result.overview.field_sizes.map(([field, count]) => ({
                label: FIELD_LABEL[field] ?? field.replace(/_/g, ' '),
                value: count,
              }))}
            />
          </div>

          <StructuredListWrapper isCondensed selection={false}>
            <StructuredListHead>
              <StructuredListRow head>
                <StructuredListCell head>Fetch this</StructuredListCell>
                <StructuredListCell head>Parts settled</StructuredListCell>
                <StructuredListCell head>What it would settle</StructuredListCell>
                <StructuredListCell head> </StructuredListCell>
              </StructuredListRow>
            </StructuredListHead>
            <StructuredListBody>
              {surface.rows.map((row) => {
                const parts = partsOf(row.detail);
                const isOpen = expanded === row.key;
                return (
                  <StructuredListRow key={row.key}>
                    <StructuredListCell noWrap>
                      {FIELD_LABEL[row.key] ?? row.key.replace(/_/g, ' ')}
                    </StructuredListCell>
                    <StructuredListCell className="sea-figure">
                      <Tag type="warm-gray" size="sm">{parts.length}</Tag>
                    </StructuredListCell>
                    <StructuredListCell>
                      {row.sentence}
                      {isOpen && parts.length > 0 && (
                        <div style={{ marginTop: '0.75rem' }}>
                          {/* A COPY BUTTON, NOT A WALL OF PART NUMBERS.
                              Nobody reads 26 identifiers in running prose;
                              they paste them into the system they are about
                              to query. */}
                          <CodeSnippet
                            type="multi"
                            feedback="Copied"
                            minCollapsedNumberOfRows={3}
                            maxCollapsedNumberOfRows={6}
                          >
                            {parts.join('\n')}
                          </CodeSnippet>
                        </div>
                      )}
                    </StructuredListCell>
                    <StructuredListCell>
                      <Button
                        kind="ghost"
                        size="sm"
                        onClick={() => setExpanded(isOpen ? null : row.key)}
                      >
                        {isOpen ? 'Hide parts' : `Show ${parts.length} parts`}
                      </Button>
                    </StructuredListCell>
                  </StructuredListRow>
                );
              })}
            </StructuredListBody>
          </StructuredListWrapper>

          <Button
            kind="ghost"
            style={{ marginTop: '1rem' }}
            onClick={() => downloadCsv(
              'what-to-check.csv',
              ['field', 'part'],
              surface.rows.flatMap((row) =>
                partsOf(row.detail).map((part) => [row.key, part])))}
          >
            Export CSV
          </Button>
        </>
      )}
    </section>
  );
}
