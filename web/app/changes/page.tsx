'use client';
/**
 * What changed: two runs, compared. The row is a CHANGE.
 *
 * WHY THIS SURFACE EXISTS. A single run answers "what is exposed". The question
 * a person is actually asked on a Monday is "what is exposed that was not last
 * week", and answering it by reading two screens side by side is how a new
 * single source goes unnoticed for a month.
 *
 * THE THREE GROUPS ARE NOT A RANKING, they are three different instructions:
 *
 *   worse        act on these
 *   no verdict   read these, because nobody can say whether they are worse.
 *                A measure that stopped being answerable, or a bound that moved
 *                in a direction that says nothing about the true figure. These
 *                are the rows a diff usually drops and they are the ones that
 *                most often matter.
 *   scope        a part that was not assessed this time did NOT get better, and
 *                keeping it separate is what stops somebody improving the
 *                numbers by scoping harder.
 */
import { useCallback, useEffect, useState } from 'react';
import {
  Button, DataTable, InlineNotification, Select, SelectItem, Table, TableBody,
  TableCell, TableContainer, TableHead, TableHeader, TableRow, TableToolbar,
  TableToolbarContent, Tag,
} from '@carbon/react';
import { useRun } from '@/components/RunProvider';
import { Empty, Failed, Loading } from '@/components/States';
import { fetchChanges, fetchRuns } from '@/lib/api';
import { downloadCsv } from '@/lib/csv';
import { CHANGE_LABEL, DIMENSION_LABEL, SCOPE_KINDS } from '@/lib/labels';
import { formatNumber, isUnbounded } from '@/lib/measure';
import type { Change, Comparison, Measure } from '@/lib/types';

interface RunRow { id: string; created_at: string; dataset: string }

function show(value: Measure): string {
  if (value === null || value === undefined) return 'not enough data to say';
  if (isUnbounded(value)) return 'unbounded';
  if (Array.isArray(value)) return value.map(show).join(' / ');
  if (typeof value === 'string') return value.replace(/_/g, ' ');
  const text = formatNumber(value);
  return text === null ? String(value) : Number(text).toLocaleString();
}

export default function WhatChanged() {
  const { result } = useRun();
  const [runs, setRuns] = useState<RunRow[] | null>(null);
  const [before, setBefore] = useState('');
  const [after, setAfter] = useState('');
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchRuns().then((answer) => {
      setRuns(answer.runs);
      // Newest first from the API, so the newest is the natural "after" and the
      // one before it the natural "before". Both stay changeable: a default
      // that cannot be changed is a comparison somebody else chose.
      if (answer.runs.length >= 2) {
        setAfter(answer.runs[0].id);
        setBefore(answer.runs[1].id);
      } else if (answer.runs.length === 1) {
        setAfter(answer.runs[0].id);
      }
    }).catch(setError);
  }, [result]);

  const compare = useCallback(() => {
    if (!before || !after) return;
    setBusy(true);
    setError(null);
    fetchChanges(before, after)
      .then(setComparison)
      .catch(setError)
      .finally(() => setBusy(false));
  }, [before, after]);

  if (error !== null && comparison === null) {
    return <Failed error={error} onRetry={compare} />;
  }
  if (runs === null) return <Loading label="Reading the run history." />;

  return (
    <section className="sea-section">
      <h2 className="sea-section__heading">What changed</h2>
      <p className="sea-section__note">
        Two runs, compared. A part that was not assessed this time did not get
        better, and a figure that stopped being answerable has not fallen, so
        those are kept apart from things that genuinely got worse.
      </p>

      {runs.length < 2 ? (
        <Empty title="There is only one run to compare">
          Score a second dataset, or re-score after an extract changes, and this
          page will say what moved between them.
        </Empty>
      ) : (
        <>
          <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end',
                        flexWrap: 'wrap', marginBottom: '1.5rem' }}>
            <div style={{ minWidth: '18rem' }}>
              <Select id="before" labelText="Earlier run" value={before}
                      onChange={(event) => setBefore(event.target.value)}>
                {runs.map((row) => (
                  <SelectItem key={row.id} value={row.id}
                              text={`${row.dataset} — ${new Date(row.created_at).toLocaleString()}`} />
                ))}
              </Select>
            </div>
            <div style={{ minWidth: '18rem' }}>
              <Select id="after" labelText="Later run" value={after}
                      onChange={(event) => setAfter(event.target.value)}>
                {runs.map((row) => (
                  <SelectItem key={row.id} value={row.id}
                              text={`${row.dataset} — ${new Date(row.created_at).toLocaleString()}`} />
                ))}
              </Select>
            </div>
            <Button kind="primary" onClick={compare}
                    disabled={busy || !before || !after}>
              {busy ? 'Comparing' : 'Compare'}
            </Button>
          </div>

          {error !== null && <Failed error={error} onRetry={compare} />}

          {comparison && <Result comparison={comparison} />}
        </>
      )}
    </section>
  );
}

function Result({ comparison }: { comparison: Comparison }) {
  const scope = comparison.changes.filter((c) => SCOPE_KINDS.includes(c.kind));
  const worse = comparison.changes.filter(
    (c) => c.worsened === true && !SCOPE_KINDS.includes(c.kind));
  const better = comparison.changes.filter(
    (c) => c.worsened === false && !SCOPE_KINDS.includes(c.kind));
  const unjudged = comparison.changes.filter(
    (c) => c.worsened === null && !SCOPE_KINDS.includes(c.kind));

  if (comparison.changes.length === 0) {
    return (
      <Empty title="Nothing changed between these two runs">
        Every verdict, every figure and every group is the same. That is an
        answer about the data, not an empty screen.
      </Empty>
    );
  }

  return (
    <div className="sea-stack">
      {/* TWO RUNS OF DIFFERENT DATA ARE NOT A TREND, so which two is said
          before anything that moved. */}
      <InlineNotification
        kind="info"
        lowContrast
        hideCloseButton
        title="What was compared"
        subtitle={
          `${comparison.before.dataset} (${comparison.before.provenance.parts_assessed} `
          + `parts assessed) against ${comparison.after.dataset} `
          + `(${comparison.after.provenance.parts_assessed} parts assessed).`}
      />

      <Group title="Worse than last time" rows={worse}
             note="Act on these." />
      <Group
        title="Nobody can say whether these are worse"
        rows={unjudged}
        note={'A figure that stopped being answerable has not fallen, and two '
              + 'bounds can both move while the true figures do not. These are '
              + 'reported without a verdict rather than dropped.'} />
      <Group title="Better than last time" rows={better}
             note="Recorded so the list is not only bad news." />
      <Group
        title="Not comparable: the scope changed"
        rows={scope}
        note={'A part that was not assessed this time did not get better. '
              + 'Kept separate so the exposure count cannot be improved by '
              + 'narrowing the question.'} />
    </div>
  );
}

const HEADERS = [
  { key: 'what', header: 'What' },
  { key: 'subject', header: 'Part or group' },
  { key: 'measure', header: 'Measure' },
  { key: 'before', header: 'Was' },
  { key: 'after', header: 'Now' },
];

function Group({ title, rows, note }: {
  title: string; rows: Change[]; note: string;
}) {
  if (rows.length === 0) return null;
  const table = rows.map((change, index) => ({
    id: `${change.kind}-${change.subject}-${change.dimension}-${index}`,
    what: CHANGE_LABEL[change.kind] ?? change.kind.replace(/_/g, ' '),
    subject: change.subject,
    measure: change.dimension
      ? (DIMENSION_LABEL[change.dimension] ?? change.dimension)
      : '—',
    before: show(change.before),
    after: show(change.after),
  }));

  return (
    <section>
      <h3 className="sea-chart__title">
        {title} <Tag type="outline" size="sm">{rows.length}</Tag>
      </h3>
      <p className="sea-section__note">{note}</p>
      <DataTable rows={table} headers={HEADERS} isSortable>
        {({ rows: shown, headers, getTableProps, getHeaderProps,
            getRowProps }) => (
          <TableContainer>
            <TableToolbar>
              <TableToolbarContent>
                <Button
                  kind="ghost"
                  onClick={() => downloadCsv(
                    `${title.toLowerCase().replace(/[^a-z]+/g, '-')}.csv`,
                    HEADERS.map((header) => header.header),
                    table.map((row) => HEADERS.map(
                      (header) => String(
                        (row as unknown as Record<string, unknown>)[header.key]
                        ?? ''))))}
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
                        <TableCell key={datum.id}>{datum.value}</TableCell>
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
  );
}
