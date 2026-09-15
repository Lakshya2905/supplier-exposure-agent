'use client';
/**
 * The run context strip. Which data, scored when, and how much of it.
 *
 * REPLACES THREE COLLAPSED DROPDOWNS repeated on every page of the Streamlit
 * app. Provenance that is three clicks away on four pages is provenance nobody
 * reads; the same facts on one line under the header are read once and then
 * available whenever a reader wonders which run they are looking at.
 */
import { Button, Tag } from '@carbon/react';
import { Renew } from '@carbon/react/icons';
import { useRun } from './RunProvider';
import { DataPanel } from './DataPanel';
import { ScopePicker } from './ScopePicker';

export function RunBar() {
  const { result, loading, reload } = useRun();

  return (
    <div className="sea-runbar">
      <div className="sea-runbar__item">
        <span className="sea-runbar__label">Dataset</span>
        <span className="sea-runbar__value">
          {result ? result.run.dataset : 'loading'}
        </span>
      </div>
      <div className="sea-runbar__item">
        <span className="sea-runbar__label">Scored</span>
        <span className="sea-runbar__value">
          {result ? new Date(result.run.created_at).toLocaleString() : '—'}
        </span>
      </div>
      <div className="sea-runbar__item">
        <span className="sea-runbar__label">Parts scored</span>
        <span className="sea-runbar__value">
          {result ? result.run.counts.parts_scored.toLocaleString() : '—'}
        </span>
      </div>
      <div className="sea-runbar__item">
        <span className="sea-runbar__label">Run</span>
        <span className="sea-runbar__value">{result?.run.id ?? '—'}</span>
      </div>
      {/* SHORT ENOUGH NOT TO TRUNCATE. Carbon caps a Tag's width and clips
          with an ellipsis, and "1,051 of 2,072 results need a per…" is a figure
          a reader cannot use. */}
      {result && (
        <Tag type="cool-gray" size="sm">
          {result.run.counts.deferring.toLocaleString()} of{' '}
          {result.run.counts.dimension_results.toLocaleString()} need a person
        </Tag>
      )}
      {result?.scope.is_scoped && (
        // A SCOPED RUN SAYS SO WHEREVER THE READER IS. The count of what was
        // left out belongs beside the count of what was assessed, because a
        // screen showing 40 parts looks identical whether the other 11,960 are
        // fine or were never opened.
        <Tag type="warm-gray" size="sm">
          {result.scope.parts_excluded.length.toLocaleString()} parts not
          assessed
        </Tag>
      )}
      <div style={{ marginInlineStart: 'auto', display: 'flex', gap: '0.5rem' }}>
        <ScopePicker />
        <DataPanel />
        <Button
          kind="ghost"
          size="sm"
          renderIcon={Renew}
          disabled={loading}
          onClick={reload}
        >
          Re-score
        </Button>
      </div>
    </div>
  );
}
