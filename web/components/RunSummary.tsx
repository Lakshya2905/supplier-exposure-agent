'use client';
/**
 * The run summary, laid out for paper.
 *
 * A REAL PDF, THROUGH THE BROWSER'S OWN PRINT PATH, and no library. The
 * alternatives were jsPDF, which redraws the page into a canvas and loses the
 * text, and a server-side renderer, which means running a browser on the
 * backend to print a page the frontend already has. `window.print()` into "Save
 * as PDF" produces selectable, searchable, vector text with the fonts already
 * loaded, and it is what an enterprise user does anyway.
 *
 * WHAT GOES ON PAPER IS WHAT A RUN CLAIMS, NOT WHAT IT FOUND. A PDF outlives
 * the screen it came from and will be read by somebody who cannot ask which run
 * it was, so the provenance is the first thing on it: which dataset, which
 * files with their digests, what was assessed and what was not. The findings
 * come after that, and every one of them keeps its unit.
 *
 * THE NO-COMPOSITE STANCE SURVIVES THE PRINTER. There is no total on this sheet
 * and no place to put one, and the standing sentence about why is printed with
 * the figures rather than left behind on the screen. A summary that quietly
 * combined what the interface refuses to would be the composite escaping
 * through the export button.
 */
import { Button } from '@carbon/react';
import { Printer } from '@carbon/react/icons';
import { DIMENSION_LABEL, DIMENSION_UNIT, labelFor } from '@/lib/labels';
import { STANDING_COPY } from './Measures';
import type { ScoreResult } from '@/lib/types';

export function PrintButton() {
  return (
    <Button kind="ghost" size="sm" renderIcon={Printer}
            onClick={() => window.print()}>
      Export PDF
    </Button>
  );
}

export function RunSummary({ result }: { result: ScoreResult }) {
  const { run, overview, scope } = result;
  const clusters = overview.cluster_sizes ?? [];

  return (
    <section className="sea-print-only" aria-hidden="true">
      <h1>Supplier Exposure Agent — run summary</h1>

      <h2>What was read</h2>
      <table className="sea-print-table">
        <tbody>
          <tr><th>Dataset</th><td>{run.dataset}</td></tr>
          <tr><th>Scored</th><td>{new Date(run.created_at).toUTCString()}</td></tr>
          <tr><th>Run</th><td>{run.id}</td></tr>
          <tr><th>Parts assessed</th><td>{run.counts.parts_scored.toLocaleString()}</td></tr>
        </tbody>
      </table>

      <table className="sea-print-table">
        <thead>
          <tr><th>File</th><th>System of record</th><th>Pulled</th><th>Digest</th></tr>
        </thead>
        <tbody>
          {run.files.map((file) => {
            const extract = result.extracts[file.name];
            return (
              <tr key={file.name}>
                <td>{file.name}</td>
                <td>{extract ? extract[0] : 'not in the extract manifest'}</td>
                <td>{extract ? extract[1] : '—'}</td>
                <td><code>{file.sha256.slice(0, 12)}</code></td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <h2>What this run did not assess</h2>
      <p>{scope.sentence}</p>
      {result.surfaces.exposure.coverage?.notes.map((note) => (
        <p key={note.subject}>{note.count.toLocaleString()} — {note.sentence}</p>
      ))}

      <h2>The measures, each in its own unit</h2>
      <table className="sea-print-table">
        <thead>
          <tr><th>Measure</th><th>Unit</th><th>With a figure</th><th>Not established</th></tr>
        </thead>
        <tbody>
          {overview.dimension_series.map((series) => {
            const assessed = series.values.length
              + Object.values(series.categories).reduce((a, b) => a + b, 0)
              + series.unbounded;
            return (
              <tr key={series.dimension}>
                <td>{DIMENSION_LABEL[series.dimension] ?? series.dimension}</td>
                <td>{DIMENSION_UNIT[series.dimension] ?? series.unit}</td>
                <td>{assessed.toLocaleString()}</td>
                <td>{series.unknown.toLocaleString()}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="sea-print-standing">{STANDING_COPY}</p>

      <h2>Parts that matched a named pattern</h2>
      <table className="sea-print-table">
        <thead>
          <tr><th>Part</th><th>Finding</th></tr>
        </thead>
        <tbody>
          {result.surfaces.exposure.layers.flatMap((layer) =>
            layer.flatMap((group) => group.rows)).map((row) => (
              <tr key={row.key}>
                <td>{row.key}</td>
                <td>{row.sentence}</td>
              </tr>
          ))}
        </tbody>
      </table>

      <h2>Judgments waiting for a person</h2>
      <p>
        Grouping is a modelling judgment, so these are proposed and never
        applied automatically. {clusters.length} groups await confirmation.
      </p>
      <table className="sea-print-table">
        <thead>
          <tr><th>Group</th><th>Grouped by</th><th>Parts covered</th></tr>
        </thead>
        <tbody>
          {clusters.map(([key, size, basis]) => (
            <tr key={`${basis}-${key}`}>
              <td>{labelFor(String(key), overview.region_labels)}</td>
              <td>{basis}</td>
              <td>{size}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="sea-print-standing">
        Synthetic data unless this run reads your own extract. Every figure above
        keeps its unit and none of them is combined with another.
      </p>
    </section>
  );
}
