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
import { CountBar, ChartOrAbsence, Distribution } from '@/components/Charts';
import { Failed, Loading } from '@/components/States';
import { STANDING_COPY } from '@/components/Measures';
import { DIMENSION_LABEL, DIMENSION_UNIT, labelFor } from '@/lib/labels';
import type { DimensionSeries } from '@/lib/types';

export default function Overview() {
  const { result, loading, error, reload } = useRun();

  if (loading && !result) return <Loading label="Scoring the dataset." />;
  if (!result) return <Failed error={error} onRetry={reload} />;

  const { overview } = result;

  return (
    <>
      {error !== null && <Failed error={error} onRetry={reload} />}

      <section className="sea-section">
        <h2 className="sea-section__heading">Overview</h2>
        <p className="sea-section__note">
          The shape of the whole set. Nothing on this page is a decision: to act
          on a part go to Exposure, to find the one fact that settles the most
          go to What to check, and to sign off a judgment go to Review.
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
          The six measures, each in its own unit
        </h3>
        <p className="sea-section__note">
          Six separate axes on purpose. No chart here puts two measures
          together, because there is no unit in which days and finished-good
          units are the same quantity. Three of them are in days and they are
          still three axes: waiting a disruption out, resourcing around it and
          covering it from stock are different questions that share a unit.
        </p>
        <div className="sea-charts">
          {overview.dimension_series.map((series) => (
            <SeriesPanel key={series.dimension} series={series} />
          ))}
        </div>
        <p className="sea-standing">{STANDING_COPY}</p>
      </section>

      <section className="sea-section">
        <h3 className="sea-section__heading">Where the suppliers are</h3>
        <p className="sea-section__note">
          Counts per region, including any region the data names that no map
          would draw. Grouping parts by region is one of two readings of
          correlated exposure, and the other is by supplier; they answer
          different questions and neither settles the other.
        </p>
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
        <p className="sea-section__note">
          These are properties of the data and of deliberate design decisions,
          not faults. A part counted here was not scored on that question, and
          the reason is stated rather than implied.
        </p>
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

function SeriesPanel({ series }: { series: DimensionSeries }) {
  const categorical = Object.keys(series.categories).length > 0;
  const assessed = series.values.length
    + Object.values(series.categories).reduce((a, b) => a + b, 0)
    + series.unbounded;

  // A PAIR IS DRAWN AS ITS FIRST HALF AND SAYS SO. `wait_out_days` carries
  // quoted and worst case, both in days. Drawing one without saying which would
  // be the tool choosing which half counts; drawing both on one axis is fine
  // because they are one measure, but a histogram of pairs is unreadable, so
  // the quoted figure is charted and the caption names the choice.
  const numbers = series.values.map(
    (value) => (Array.isArray(value) ? value[0] : value));

  return (
    <div className="sea-chart">
      <div className="sea-chart__title">
        {DIMENSION_LABEL[series.dimension] ?? series.dimension}
      </div>
      <div className="sea-chart__unit">
        {DIMENSION_UNIT[series.dimension] ?? series.unit.replace(/_/g, ' ')}
        {series.values.length > 0 && Array.isArray(series.values[0])
          && ' — quoted figure drawn'}
      </div>
      <ChartOrAbsence assessed={assessed} unknown={series.unknown}>
        {categorical ? (
          <CountBar
            unit="parts"
            data={Object.entries(series.categories).map(([label, value]) => ({
              label: label.replace(/_/g, ' '), value,
            }))}
          />
        ) : (
          <Distribution values={numbers} unit={series.unit.replace(/_/g, ' ')} />
        )}
      </ChartOrAbsence>
      <p className="sea-chart__unit" style={{ marginTop: '0.5rem',
                                              marginBottom: 0 }}>
        {assessed.toLocaleString()} parts have a figure,{' '}
        {series.unknown.toLocaleString()} do not.
        {series.unbounded > 0 &&
          ` ${series.unbounded} have unbounded cover, which is an answer and is not drawn.`}
      </p>
    </div>
  );
}
