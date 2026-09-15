'use client';
/**
 * A part, opened over the list rather than instead of it.
 *
 * A TEARSHEET AND NOT A PAGE NAVIGATION, because the reader is working a list.
 * Sending them to a detail page and back loses their scroll position, their
 * search and their place, and the cost is paid on every single part they look
 * at. The list stays exactly where it was.
 *
 * FOUR THINGS IN ORDER: the finding as a sentence, the six measures uncombined,
 * what binds, and the workings. The workings are LAST and behind a disclosure,
 * because they are what a reader checks rather than what they read.
 */
import {
  Accordion, AccordionItem, StructuredListBody, StructuredListCell,
  StructuredListHead, StructuredListRow, StructuredListWrapper, Tag,
} from '@carbon/react';
import { Tearsheet } from '@carbon/ibm-products';
import { Measures, STANDING_COPY, WhatBinds } from './Measures';
import type { BindingSummary, DimensionScore, Evidence, Row } from '@/lib/types';

export interface PartDetail {
  row: Row;
  scores: Record<string, DimensionScore>;
  binding: BindingSummary;
  verdict: string;
  /** The verdict in plain words, from the API's map. Never the raw code
   *  with its underscores swapped for spaces, which is a code in disguise. */
  verdictLabel: string;
  /** Every pattern this part matched, most specific first. The table shows
   *  only the first, because dominance is subset inclusion and the first
   *  contains the rest; this is where that claim can be checked. */
  patterns: string[];
  dimensions: string[];
}

export function PartPanel({ detail }: { detail: PartDetail }) {
  const evidence = detail.row.evidence;
  return (
    <div className="sea-stack">
      <p className="sea-judgment__claim">{detail.row.sentence}</p>

      {detail.patterns.length > 1 && (
        <section>
          <h4 className="sea-chart__title">Patterns this part matches</h4>
          <ul>
            {detail.patterns.map((pattern, index) => (
              <li key={pattern} className="sea-section__note"
                  style={{ marginBottom: '0.25rem' }}>
                {pattern}
                {index === 0 && (
                  <> <Tag type="outline" size="sm">most specific</Tag></>
                )}
              </li>
            ))}
          </ul>
          <p className="sea-section__note">
            The broader ones are contained in the first: every condition they
            state, it states too.
          </p>
        </section>
      )}

      <section>
        <h4 className="sea-chart__title">The six measures, each in its own unit</h4>
        <Measures scores={detail.scores} order={detail.dimensions} />
        <p className="sea-standing">{STANDING_COPY}</p>
      </section>

      <WhatBinds summary={detail.binding} />

      <Accordion>
        <AccordionItem title="How this was worked out">
          {evidence ? <EvidencePanel evidence={evidence} /> : (
            <p className="sea-section__note">
              No evidence record was built for this row.
            </p>
          )}
        </AccordionItem>
        <AccordionItem title="Why each measure says what it says">
          <StructuredListWrapper isCondensed>
            <StructuredListBody>
              {detail.dimensions.map((dimension) => {
                const score = detail.scores[dimension];
                if (!score) return null;
                return (
                  <StructuredListRow key={dimension}>
                    <StructuredListCell noWrap>
                      {dimension.replace(/_/g, ' ')}
                    </StructuredListCell>
                    <StructuredListCell>{score.reasons[0]}</StructuredListCell>
                  </StructuredListRow>
                );
              })}
            </StructuredListBody>
          </StructuredListWrapper>
        </AccordionItem>
      </Accordion>
    </div>
  );
}

function EvidencePanel({ evidence }: { evidence: Evidence }) {
  return (
    <div className="sea-stack">
      <StructuredListWrapper isCondensed>
        <StructuredListHead>
          <StructuredListRow head>
            <StructuredListCell head>File</StructuredListCell>
            <StructuredListCell head>System of record</StructuredListCell>
            <StructuredListCell head>Pulled</StructuredListCell>
            <StructuredListCell head>Lines</StructuredListCell>
          </StructuredListRow>
        </StructuredListHead>
        <StructuredListBody>
          {evidence.sources_used.map((source) => (
            <StructuredListRow key={source.source_file}>
              <StructuredListCell noWrap>{source.source_file}</StructuredListCell>
              <StructuredListCell>{source.system_of_record}</StructuredListCell>
              <StructuredListCell>{source.retrieved_at}</StructuredListCell>
              <StructuredListCell className="sea-figure">
                {source.rows.join(', ')}
              </StructuredListCell>
            </StructuredListRow>
          ))}
        </StructuredListBody>
      </StructuredListWrapper>

      {evidence.notes.length > 0 && (
        <div>
          <h5 className="sea-chart__title">Notes</h5>
          {evidence.notes.map((note) => (
            <p key={note} className="sea-section__note">{note}</p>
          ))}
        </div>
      )}

      {evidence.absences.length > 0 && (
        <div>
          <h5 className="sea-chart__title">What is not on file</h5>
          <div className="sea-inline-tags">
            {evidence.absences.map(([kind, sentence]) => (
              <div key={sentence} className="sea-section__note">
                <Tag type="warm-gray" size="sm">{kind.replace(/_/g, ' ')}</Tag>
                {' '}{sentence}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function PartTearsheet({ detail, open, onClose }: {
  detail: PartDetail | null; open: boolean; onClose: () => void;
}) {
  return (
    <Tearsheet
      open={open && detail !== null}
      onClose={onClose}
      title={detail?.row.key ?? ''}
      description={detail?.verdictLabel ?? ''}
      hasCloseIcon
      closeIconDescription="Close"
      influencerPosition="right"
      influencerWidth="narrow"
    >
      <div style={{ padding: '1.5rem' }}>
        {detail && <PartPanel detail={detail} />}
      </div>
    </Tearsheet>
  );
}
