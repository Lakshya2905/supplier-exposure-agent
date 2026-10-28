'use client';
/**
 * Overview: the shape of the whole set. DECIDES NOTHING.
 *
 * That is the job and the constraint together. Nothing here is actionable and
 * nothing is ranked, because a reader who acts off this page is acting off an
 * aggregate. Every route to a decision runs through Exposure, What to check or
 * Review, where the row is a part, a field or a cluster and the workings are a
 * click away.
 */
import {
  DataTable, Table, TableBody, TableCell, TableContainer, TableHead,
  TableHeader, TableRow, Tag,
} from '@carbon/react';
import { useRun } from '@/components/RunProvider';
import { RegionMap } from '@/components/RegionMap';
import { Failed, Loading } from '@/components/States';
import { STANDING_COPY } from '@/components/Measures';
import { labelFor } from '@/lib/labels';
import { measureRows } from '@/lib/measures';

export default function Overview() {
  const { result, loading, error, reload } = useRun();

  if (loading && !result) return <Loading label="Scoring the dataset." />;
  if (!result) return <Failed error={error} onRetry={reload} />;

  const { overview } = result;
  const rows = measureRows(overview.dimension_series);

  return (
    <>
      {error !== null && <Failed error={error} onRetry={reload} />}

      <section className="sea-section">
        <h2 className="sea-section__heading">Overview</h2>
        <p className="sea-section__note">
          The shape of the whole set. Nothing on this page is a decision.
        </p>
        <div className="sea-metrics">
          {overview.tiles.map((tile) => (
            <div className="sea-metric" key={tile.label}>
              <div className="sea-metric__label">{tile.label}</div>
              <div className="sea-metric__value">
                {tile.value.toLocaleString()}
              </div>
              <div className="sea-metric__of">{tile.of || tile.unit}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="sea-section">
        <h3 className="sea-section__heading">
          The seven measures, each in its own unit
        </h3>
        <p className="sea-section__note">
          Seven separate axes on purpose, and no chart puts two measures on
          one. Sharing a unit is not being the same quantity: waiting a
          disruption out, resourcing around it and covering it from stock are
          all in days and are three different questions.
        </p>
        {/*
          A TABLE, AND DELIBERATELY NOT A SORTABLE ONE. Seven measures in seven
          units, in the fixed order `scoring.DIMENSIONS` declares. A control
          that ordered them by "not established" would rank the measures
          against each other, which is the thing this page exists to refuse:
          DESIGN.md's anti-ranking contract puts it plainly, "a reviewer who
          sorts by dimension three has declared dimension three the ranking".
          So this is a plain Carbon table with no toolbar and no header
          buttons, never a DataTable.

          IT REPLACED SEVEN HISTOGRAMS. What those drew was a distribution;
          what they were read for was the caption underneath, which said how
          many parts each measure had a figure for. The caption is a column
          now, and seven of them read at a glance where seven captions did not.
        */}
        <Table size="sm">
          <TableHead>
            <TableRow>
              <TableHeader>Measure</TableHeader>
              <TableHeader>Unit</TableHeader>
              <TableHeader>Parts with a figure</TableHeader>
              <TableHeader>Parts not established</TableHeader>
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.dimension}>
                <TableCell>{row.label}</TableCell>
                <TableCell>{row.unit}</TableCell>
                <TableCell>{row.assessed.toLocaleString()}</TableCell>
                <TableCell>{row.unknown.toLocaleString()}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {/* UNBOUNDED IS COUNTED AS A FIGURE, AND SAID OUT LOUD WHERE IT
            HAPPENS. Stock with nothing consuming it lasts indefinitely, which
            is an answer rather than an absence. It sits inside the figure
            column, and this names it so that column is not quietly carrying
            two kinds of thing. The charts had to mention it separately because
            a histogram cannot draw infinity; a table has no such problem. */}
        {rows.filter((row) => row.unbounded > 0).map((row) => (
          <p key={row.dimension} className="sea-section__note">
            {row.unbounded.toLocaleString()} of the figures for{' '}
            {row.label.toLowerCase()} are unbounded, which is an answer and is
            counted as one.
          </p>
        ))}
        <p className="sea-standing">{STANDING_COPY}</p>
      </section>

      <section className="sea-section">
        <h3 className="sea-section__heading">Where the suppliers are</h3>
        <p className="sea-section__note">
          Grouping parts by region is one of two readings of shared exposure,
          and the other is by supplier. They answer different questions and
          neither settles the other. The table below carries every region the
          data names, including any the map cannot draw.
        </p>
        <RegionMap result={result} />
        <div style={{ height: '1.5rem' }} />
        <DataTable rows={overview.regions.map((region) => ({
          id: region.region,
          region: labelFor(region.region, overview.region_labels),
          suppliers: region.suppliers,
          parts: region.parts,
          exposed: region.exposed_parts,
          countries: region.countries.join(', ') || 'not drawn on any map',
        }))} headers={[
          { key: 'region', header: 'Region' },
          { key: 'suppliers', header: 'Suppliers' },
          { key: 'parts', header: 'Parts with a supplier here' },
          { key: 'exposed', header: 'Single-source parts' },
          { key: 'countries', header: 'Countries' },
        ]}>
          {({ rows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer>
              <Table {...getTableProps()} size="sm">
                <TableHead>
                  <TableRow>
                    {headers.map((header) => {
                      const props = getHeaderProps({ header });
                      const { key, ...rest } = props as typeof props & { key?: string };
                      return <TableHeader key={header.key} {...rest}>{header.header}</TableHeader>;
                    })}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {rows.map((row) => {
                    const props = getRowProps({ row });
                    const { key, ...rest } = props as typeof props & { key?: string };
                    return (
                      <TableRow key={row.id} {...rest}>
                        {row.cells.map((cell) => (
                          <TableCell key={cell.id}>{cell.value}</TableCell>
                        ))}
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </DataTable>
      </section>

      <section className="sea-section">
        <h3 className="sea-section__heading">What this run did not assess</h3>
        {/* THE SCOPE FIRST, because it is the largest thing a run can leave
            out and the one a reader is least likely to guess. */}
        <p className="sea-section__note">{result.scope.sentence}</p>
        <div className="sea-inline-tags">
          {/* A div, not a p: Carbon's Tag is a div and nesting one in a p is
              invalid HTML that React fixes by moving the node. */}
          {result.surfaces.exposure.coverage?.notes.map((note) => (
            <div key={note.subject} className="sea-section__note">
              <Tag type={note.kind === 'not_applicable' ? 'cool-gray' : 'warm-gray'}
                   size="sm">
                {note.count.toLocaleString()}
              </Tag>{' '}
              {note.sentence}
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
