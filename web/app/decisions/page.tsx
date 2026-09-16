'use client';
/**
 * The decision log, as a first-class view.
 *
 * IT ALREADY RECORDED ALL OF THIS AND NOTHING SHOWED IT. Who decided what, when
 * and why is the thing a tool like this is trusted for, and it was reachable
 * only by reading a JSONL file on the server.
 *
 * THE SENTENCE IS RENDERED ON READ, NEVER STORED. The file holds structure and
 * no prose, so a wording change reaches every decision ever recorded. This page
 * displays what `render()` produced a moment ago and assembles nothing itself.
 */
import { useCallback, useEffect, useState } from 'react';
import {
  Button, DataTable, Table, TableBody, TableCell, TableContainer, TableHead,
  TableHeader, TableRow, TableToolbar, TableToolbarContent,
  TableToolbarSearch, Tag,
} from '@carbon/react';
import { Empty, Failed, Loading } from '@/components/States';
import { fetchDecisions } from '@/lib/api';
import { downloadCsv } from '@/lib/csv';
import type { SortRowParams } from
  '@carbon/react/lib/components/DataTable/state/sorting';
import type { DecisionEvent } from '@/lib/types';

const HEADERS = [
  { key: 'at', header: 'When' },
  { key: 'decided_by', header: 'Who' },
  { key: 'sku_id', header: 'Subject' },
  { key: 'status', header: 'Decision' },
  { key: 'reason_code', header: 'Reason' },
  { key: 'note', header: 'Note' },
  { key: 'member_count', header: 'Parts covered' },
];

export default function Decisions() {
  const [entries, setEntries] = useState<DecisionEvent[] | null>(null);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(() => {
    setError(null);
    fetchDecisions()
      .then((answer) => setEntries(answer.decisions))
      .catch(setError);
  }, []);

  useEffect(load, [load]);

  if (error !== null) return <Failed error={error} onRetry={load} />;
  if (entries === null) return <Loading label="Reading the decision log." />;

  // WHEN SORTS BY THE INSTANT, NOT BY THE TEXT OF THE DATE. `toLocaleString`
  // renders "9/16/2026, 4:49:49 AM", and Carbon's default comparator collates
  // that as characters: it reads 9 against 10 and puts September after October,
  // and it has no idea the year is the third field. An append-only log whose
  // "When" column can be sorted into the wrong order is the one column in this
  // application that must not be.
  const when = new Map(entries.map(
    (entry) => [String(entry.event_id), Date.parse(entry.at)]));

  const sortRow = (a: string | number, b: string | number, meta: SortRowParams) => {
    const ascending = meta.sortDirection === meta.sortStates.ASC;
    if (meta.key !== 'at') {
      return ascending ? meta.compare(a, b, meta.locale)
                       : meta.compare(b, a, meta.locale);
    }
    const { rowIds } = meta as SortRowParams & { rowIds: string[] };
    const [left, right] = rowIds.map((id) => when.get(id) ?? 0);
    const order = left < right ? -1 : left > right ? 1 : 0;
    return ascending ? order : -order;
  };

  const rows = entries.map((entry) => ({
    id: String(entry.event_id),
    at: new Date(entry.at).toLocaleString(),
    decided_by: entry.decided_by,
    sku_id: entry.sku_id,
    status: entry.status,
    reason_code: entry.reason_code || '—',
    note: entry.note || '—',
    member_count: entry.member_count,
  }));

  return (
    <section className="sea-section">
      <h2 className="sea-section__heading">Decision log</h2>
      <p className="sea-section__note">
        Every judgment a person recorded, in the order they were made. The log
        is append-only: a changed mind is a new entry citing the old one, never
        an edit over it, which is what makes it a trail rather than a document.
      </p>

      {rows.length === 0 ? (
        <Empty title="Nobody has recorded a decision yet">
          Judgments waiting for a person are on the Review surface. Confirming
          or rejecting one writes the first entry here.
        </Empty>
      ) : (
        <DataTable rows={rows} headers={HEADERS} isSortable sortRow={sortRow}>
          {({ rows: shown, headers, getTableProps, getHeaderProps,
              getRowProps, onInputChange }) => (
            <TableContainer>
              <TableToolbar>
                <TableToolbarContent>
                  <TableToolbarSearch onChange={onInputChange} persistent
                                      placeholder="Search who, subject or reason" />
                  <Button kind="ghost" onClick={load}>Refresh</Button>
                  <Button
                    kind="ghost"
                    onClick={() => downloadCsv(
                      'decisions.csv',
                      [...HEADERS.map((header) => header.header), 'sentence'],
                      entries.map((entry) => [
                        entry.at, entry.decided_by, entry.sku_id, entry.status,
                        entry.reason_code, entry.note,
                        String(entry.member_count), entry.sentence]))}
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
                    return (
                      <TableRow key={row.id} {...rest}>
                        {row.cells.map((datum) => (
                          <TableCell key={datum.id}>
                            {datum.info.header === 'status' ? (
                              <Tag
                                type={datum.value === 'approved'
                                  ? 'green' : 'red'}
                                size="sm"
                              >
                                {datum.value === 'approved'
                                  ? 'confirmed' : 'rejected'}
                              </Tag>
                            ) : datum.value}
                          </TableCell>
                        ))}
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </DataTable>
      )}

      {rows.length > 0 && (
        <div className="sea-stack" style={{ marginTop: '1.5rem' }}>
          <h3 className="sea-chart__title">As sentences</h3>
          {entries.map((entry) => (
            <p key={entry.event_id} className="sea-section__note">
              {entry.sentence}
            </p>
          ))}
        </div>
      )}
    </section>
  );
}
