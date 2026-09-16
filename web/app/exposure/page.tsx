'use client';
/**
 * Exposure: what is worst. The row is a part.
 *
 * A TABLE, NOT PARAGRAPHS. The Streamlit surface renders a full sentence per
 * part in running prose, which is unscannable at three hundred rows: a reader
 * cannot compare two parts without reading two paragraphs. The sentence has not
 * gone anywhere, it has moved to the Tearsheet, where it is read once about one
 * part, which is the only place a sentence is the right shape.
 *
 * NO SORT IS APPLIED BY DEFAULT, and the caption says so. Carbon's DataTable
 * offers column sort and that is fine: a reader who sorts by cover has asked a
 * question about cover. What must not happen is the tool arriving pre-sorted by
 * something, because a default order is read as a ranking within minutes and
 * nobody checks which column it was.
 */
import { useMemo, useState } from 'react';
import {
  Button, DataTable, Table, TableBody, TableCell, TableContainer, TableHead,
  TableHeader, TableRow, TableToolbar, TableToolbarContent,
  TableToolbarSearch, Tag,
} from '@carbon/react';
import { useRun } from '@/components/RunProvider';
import { Empty, Failed, Loading, NotConfigured } from '@/components/States';
import { PartTearsheet } from '@/components/PartTearsheet';
import type { PartDetail } from '@/components/PartTearsheet';
import { boundPrefix } from '@/components/Absence';
import { downloadCsv } from '@/lib/csv';
import { labelFor, RUN_OUT } from '@/lib/labels';
import {
  boundIsTrivial, formatNumber, isUnbounded, toNumber,
} from '@/lib/measure';
import { exposedRows } from '@/lib/exposed';
import type { DimensionScore } from '@/lib/types';

const HEADERS = [
  { key: 'part', header: 'Part' },
  { key: 'pattern', header: 'Pattern' },
  // DIRECTLY AFTER THE PATTERN, because it is the line a planner acts on. The
  // pattern says what kind of exposure this is; this says whether it bites
  // before a replacement order can land.
  { key: 'runOut', header: 'Stock vs next delivery' },
  { key: 'stops', header: 'How much of the build stops' },
  { key: 'cover', header: 'How long stock lasts' },
  { key: 'lead', header: 'Worst case lead time' },
  { key: 'supplier', header: 'Supplier' },
  { key: 'region', header: 'Region' },
];

const UNKNOWN = 'not enough data to say';

/** A cell that is a measure, with its absence stated rather than blanked. */
function cell(
  score: DimensionScore | undefined,
  render: (s: DimensionScore) => string | null,
): string {
  if (!score) return 'not scored';
  if (score.completeness === 'cannot_tell') return UNKNOWN;
  if (score.completeness === 'not_applicable') return 'does not apply here';
  if (score.completeness === 'no_recovery_path') return 'no supplier on file';
  const text = render(score);
  if (text === null) return UNKNOWN;
  const prefix = boundPrefix(score.completeness);
  return prefix ? `${prefix} ${text}` : text;
}

export default function Exposure() {
  const { result, loading, error, reload } = useRun();
  const [open, setOpen] = useState<PartDetail | null>(null);

  const rows = useMemo(() => {
    if (!result) return [];
    // SHARED WITH THE PRINTED SUMMARY. See `lib/exposed.ts`: a part appears in
    // every group it matches, and the copy of this walk that lived in the
    // summary forgot to de-duplicate.
    return exposedRows(result.surfaces.exposure).map((row) => {
      const scores = result.profiles[row.key] ?? {};
      const supplier = row.evidence?.supplier_rows?.[0] as
        Record<string, string> | undefined;
      return {
        id: row.key,
        part: row.key,
        // THE MOST SPECIFIC MATCH, AND NOTHING IS LOST BY IT. The surface
        // returns archetypes in dominance-layer order and dominance is strict
        // subset inclusion of conditions, so the first match CONTAINS every
        // later one: a part told "one supplier, supplier-owned tooling, shared
        // with other parts" has already been told it has one supplier and
        // supplier-owned tooling. Listing both put the same clause in the cell
        // twice on every row and made the column unreadable.
        //
        // The count of the rest is shown rather than dropped, and the tearsheet
        // lists them all, because "implied" is an argument a reader should be
        // able to check.
        pattern: row.archetypes[0],
        // THE LABEL ONLY. The outcome code is kept beside it for the tag type
        // and never painted: a reader sees "Runs out first", not an enum.
        // OPTIONAL ON THE MAP ITSELF, not only on the entry. The frontend and
        // the backend are separate deployments on separate hosts and are
        // updated independently, so a page can genuinely meet an API that
        // predates a field. It did, during development, and the whole table
        // threw rather than showing one column short. Falling back to
        // `cannot_say` is honest here: an older API has not said.
        runOut: RUN_OUT[result.run_out?.[row.key]?.outcome ?? 'cannot_say']
          .label,
        __runOut: result.run_out?.[row.key],
        alsoMatches: row.archetypes.length - 1,
        // THE STRUCTURAL REACH, WHERE THE VOLUME COULD NOT BE COUNTED. Blast
        // radius carries two facts: how many finished goods stop, which is
        // always known, and how many units that is, which inherits the demand
        // plan's gaps. Rendering only the second gives "at least 0 units a
        // year", which is true, carries nothing, and reads as a measurement.
        // The part certainly stops those finished goods and the cell says so.
        stops: cell(scores.blast_radius, (s) => {
          const goods = toNumber(s.detail.finished_goods_blocked);
          if (boundIsTrivial(s.value, s.completeness) && goods) {
            return `${goods} finished good${goods === 1 ? '' : 's'}, none of `
              + 'them in the demand plan';
          }
          const n = toNumber(s.value);
          return n === null ? null : `${n.toLocaleString()} units a year`;
        }),
        cover: cell(scores.buffer_cover, (s) => {
          if (isUnbounded(s.value)) return 'unbounded';
          const text = formatNumber(s.value);
          return text === null ? null : `${text} days`;
        }),
        lead: cell(scores.wait_out_days, (s) => {
          if (!Array.isArray(s.value)) return null;
          const worst = formatNumber(s.value[1]);
          return worst === null ? null : `${worst} days`;
        }),
        supplier: supplier?.supplier_name ?? 'no supplier on file',
        region: supplier?.region
          ? labelFor(String(supplier.region), result.overview.region_labels)
          : 'no supplier on file',
        __row: row,
      };
    });
  }, [result]);

  if (loading && !result) return <Loading label="Scoring the dataset." />;
  if (!result) return <Failed error={error} onRetry={reload} />;

  return (
    <>
      <section className="sea-section">
        <h2 className="sea-section__heading">Exposure</h2>
        <p className="sea-section__note">
          One row per part that matched a named pattern. Every figure keeps its
          own unit and nothing here is combined. The table arrives in part
          number order, which carries no meaning; sort a column to ask a
          question about that column. Select a part for the finding, the
          workings, and what binds. A part can match several patterns; the
          column shows the most specific one, which contains the broader ones
          it also matches.
        </p>

        {/* A THRESHOLD NOBODY HAS SET IS ITS OWN KIND OF UNKNOWN, and it is
            not the same as missing data: this one is settled by editing a file,
            which is why it points at the file and the key rather than at a
            system of record. */}
        {!result.thresholds?.thresholds?.long_lead_days && (
          <NotConfigured what="Long lead" key_="thresholds.long_lead_days" />
        )}

        {rows.length === 0 ? (
          <Empty title="No part matched a named pattern">
            Every part in this run is either multi-sourced or was excluded by a
            condition the catalogue states. That is a finding about the data,
            not an empty screen.
          </Empty>
        ) : (
          <DataTable rows={rows} headers={HEADERS} isSortable>
            {({ rows: shown, headers, getTableProps, getHeaderProps,
                getRowProps, onInputChange }) => (
              <TableContainer>
                <TableToolbar>
                  <TableToolbarContent>
                    <TableToolbarSearch
                      onChange={onInputChange}
                      placeholder="Search part, pattern, supplier or region"
                      persistent
                    />
                    <Button
                      kind="ghost"
                      onClick={() => downloadCsv(
                        'exposure.csv',
                        HEADERS.map((header) => header.header),
                        rows.map((row) => HEADERS.map((header) =>
                          String((row as unknown as Record<string, unknown>)[
                            header.key] ?? ''))))}
                    >
                      Export CSV
                    </Button>
                  </TableToolbarContent>
                </TableToolbar>
                <Table {...getTableProps()} size="sm">
                  <TableHead>
                    <TableRow>
                      {headers.map((header) => {
                        const props = getHeaderProps({ header }) as
                          Record<string, unknown> & { key?: string };
                        const { key: _drop, ...rest } = props;
                        return (
                          <TableHeader key={header.key} {...rest}>
                            {header.header}
                          </TableHeader>
                        );
                      })}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {shown.map((row) => {
                      const props = getRowProps({ row }) as
                        Record<string, unknown> & { key?: string };
                      const { key: _drop, ...rest } = props;
                      const source = rows.find((entry) => entry.id === row.id);
                      return (
                        <TableRow
                          key={row.id}
                          {...rest}
                          style={{ cursor: 'pointer' }}
                          onClick={() => source && setOpen({
                            row: source.__row,
                            scores: result.profiles[row.id] ?? {},
                            binding: result.binding[row.id],
                            verdict: result.verdicts[row.id] ?? '',
                            patterns: source.__row.archetypes,
                            verdictLabel:
                              result.overview.verdict_labels[
                                result.verdicts[row.id] ?? ''
                              ] ?? result.verdicts[row.id] ?? '',
                            dimensions: result.dimensions,
                          })}
                        >
                          {row.cells.map((datum) => (
                            <TableCell key={datum.id}>
                              {datum.id.endsWith(':runOut')
                                ? (
                                  <Tag
                                    type={RUN_OUT[
                                      source?.__runOut?.outcome ?? 'cannot_say'
                                    ].tag}
                                    size="sm"
                                  >
                                    {String(datum.value)}
                                  </Tag>
                                )
                                : typeof datum.value === 'string'
                                && datum.value === UNKNOWN
                                ? <Tag type="warm-gray" size="sm">{UNKNOWN}</Tag>
                                : datum.value}
                              {datum.info.header === 'pattern'
                                && (source?.alsoMatches ?? 0) > 0 && (
                                  <span style={{ color:
                                    'var(--cds-text-helper)' }}>
                                    {' '}(+{source?.alsoMatches} broader)
                                  </span>
                              )}
                            </TableCell>
                          ))}
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
                {/* WHAT THE FILTER HIDES IS COUNTED ON SCREEN. A filtered list
                    that does not say so is a shorter list presented as the
                    whole, and every other surface still counts all of them: a
                    reader who searches here and then reads a total anywhere
                    else is comparing two different sets. `region_filter` in
                    `review_app.py` states the same sentence for the same
                    reason; this surface offered the filter without it. */}
                {shown.length < rows.length && (
                  <p className="sea-section__note" style={{ marginTop: '1rem' }}>
                    {rows.length - shown.length} of {rows.length} exposed parts
                    are hidden by this filter. Counts on every other surface are
                    for all {rows.length}.
                  </p>
                )}
              </TableContainer>
            )}
          </DataTable>
        )}
      </section>

      <PartTearsheet detail={open} open={open !== null}
                     onClose={() => setOpen(null)} />
    </>
  );
}
