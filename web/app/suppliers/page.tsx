'use client';
/**
 * The supplier as the row. Two counts, never a score.
 *
 * WHY THIS SURFACE EXISTS. Every commercial tool in this market makes the
 * supplier the primary object and this one makes the part, which is right for
 * the question it answers and leaves a buyer who owns a supplier relationship
 * reading three hundred part rows to find out what they carry.
 *
 * WHAT IT REFUSES, AND THE REFUSAL IS THE WHOLE POINT. What those tools ship
 * with the supplier row is a supplier SCORE. There is none here. Both columns
 * are counts of parts, so they share a unit and sit side by side without
 * anything being blended, and the caption says which single axis the default
 * order sorted on.
 *
 * AND WHAT IT DOES NOT CLAIM. This reads the supplier field and counts it.
 * Saying those parts are CORRELATED is a modelling judgment -- same supplier,
 * same region and same tier disagree -- and it lives in Review at a permanent
 * `recommends`. The note below says so on screen, because a table of parts
 * grouped under one supplier LOOKS like that claim whether or not it makes it.
 */
import { useMemo, useState } from 'react';
import {
  DataTable, Table, TableBody, TableCell, TableContainer, TableExpandHeader,
  TableExpandRow, TableExpandedRow, TableHead, TableHeader, TableRow,
  TableToolbar, TableToolbarContent, TableToolbarSearch, Tag,
} from '@carbon/react';
import { useRun } from '@/components/RunProvider';
import { Empty, Failed, Loading } from '@/components/States';
import { downloadCsv } from '@/lib/csv';
import { labelFor } from '@/lib/labels';
import type { SupplierRow } from '@/lib/types';

const HEADERS = [
  { key: 'supplier', header: 'Supplier' },
  { key: 'parts', header: 'Parts supplied' },
  { key: 'exposed', header: 'Parts with one real source' },
  { key: 'unsettled', header: 'Not settled' },
  { key: 'regions', header: 'Region' },
];

/** The exposed count, with its bound stated rather than implied.
 *
 *  A SMALLER NUMBER HERE READS AS A SMALLER RISK, so a supplier carrying
 *  unsettled parts must not present a bare count that can only rise. */
function exposedText(row: SupplierRow): string {
  return row.exposed_is_lower_bound
    ? `at least ${row.exposed_parts}` : String(row.exposed_parts);
}

export default function Suppliers() {
  const { result, loading, error, reload } = useRun();
  const [open, setOpen] = useState<Record<string, boolean>>({});

  const rows = useMemo(() => (result?.suppliers ?? []).map((row) => ({
    id: row.supplier,
    supplier: row.supplier,
    parts: row.parts_supplied,
    exposed: exposedText(row),
    // NOT A DASH AND NOT A BLANK. Nothing settled is a count of zero that
    // somebody can check, and absence renders at the same weight as a value.
    unsettled: row.parts_unsettled,
    regions: row.regions.map((key) => labelFor(key,
      result?.overview.region_labels ?? {})).join(', ')
      || 'no region on file',
    __row: row,
  })), [result]);

  if (error !== null && !result) return <Failed error={error} onRetry={reload} />;
  if (loading && !result) return <Loading label="Reading the supplier list." />;
  if (!result) return null;

  return (
    <section className="sea-section">
      <h2 className="sea-section__heading">Suppliers</h2>
      <p className="sea-section__note">
        One row per supplier named in the data, and two counts that are never
        combined: how much of the build depends on this supplier, and how much
        of that dependence has one real source. {result.supplier_order}
      </p>
      <p className="sea-section__note">
        This counts the supplier field. It does not say the parts under a
        supplier share a fate: whether exposure is correlated by supplier, by
        region or by tier is a judgment, and it waits for a person in Review.
      </p>

      {rows.length === 0 ? (
        <Empty title="No supplier appears in this run">
          Nothing in the data names a supplier, so there is nothing to group.
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
                    placeholder="Search supplier or region"
                  />
                  <button
                    type="button"
                    className="cds--btn cds--btn--ghost"
                    onClick={() => downloadCsv(
                      'suppliers.csv',
                      ['supplier', 'parts supplied',
                       'parts with one real source', 'not settled', 'region'],
                      rows.map((r) => [r.supplier, String(r.parts), r.exposed,
                                       String(r.unsettled), r.regions]),
                    )}
                  >
                    Export CSV
                  </button>
                </TableToolbarContent>
              </TableToolbar>
              <Table {...getTableProps()}>
                <TableHead>
                  <TableRow>
                    <TableExpandHeader aria-label="Show the parts" />
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
                    return [
                      <TableExpandRow
                        key={row.id}
                        {...rest}
                        aria-label={`Show the parts on ${row.id}`}
                        isExpanded={Boolean(open[row.id])}
                        onExpand={() => setOpen((was) => ({
                          ...was, [row.id]: !was[row.id],
                        }))}
                      >
                        {row.cells.map((datum) => (
                          <TableCell key={datum.id}>
                            {datum.id.endsWith(':exposed')
                              && Number(source?.__row.exposed_parts) > 0
                              ? (
                                <Tag type="red" size="sm">
                                  {String(datum.value)}
                                </Tag>
                              )
                              : String(datum.value)}
                          </TableCell>
                        ))}
                      </TableExpandRow>,
                      <TableExpandedRow
                        key={`${row.id}-parts`}
                        colSpan={headers.length + 1}
                      >
                        {/* THE DRILL-THROUGH. A supplier view that cannot reach
                            the parts is the index this product refuses, one
                            level up. Exposed parts are marked; the finding, the
                            workings and what binds are on Exposure. */}
                        <p className="sea-section__note">
                          {source?.__row.part_numbers.length} parts, of which
                          {' '}{exposedText(source!.__row)} have one real
                          source. Open Exposure for the finding and the
                          workings on any of them.
                        </p>
                        <div className="sea-inline-tags">
                          {source?.__row.part_numbers.map((part) => (
                            <Tag
                              key={part}
                              size="sm"
                              type={
                                source.__row.exposed_part_numbers.includes(part)
                                  ? 'red' : 'cool-gray'
                              }
                            >
                              {part}
                            </Tag>
                          ))}
                        </div>
                      </TableExpandedRow>,
                    ];
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </DataTable>
      )}
    </section>
  );
}
