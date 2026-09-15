'use client';
/**
 * Review: judgments waiting for a person. The row is a CLUSTER.
 *
 * ONE TILE PER JUDGMENT, NOT PER PART. Nine parts on one supplier is ONE
 * finding and a reviewer confirms it once. A table with a row per part would
 * make somebody confirm a single judgment nine times, which is the concrete
 * damage the denormalised view does.
 *
 * THE SHARED CAVEAT APPEARS ONCE, ABOVE THE GRID. The Streamlit surface repeats
 * the same paragraph about grouping being a modelling judgment on every card,
 * which trains a reader to skip it, which is the opposite of what it is for.
 *
 * A CONTROL EXISTS ONLY WHERE THE SERVER SENT ONE. `Row.controls` comes from
 * the API and is empty for anything that executes. This page never constructs a
 * button from a row's shape, because an affordance invented in the frontend is
 * an autonomy claim made by the frontend.
 */
import { useEffect, useMemo, useState } from 'react';
import {
  Button, InlineNotification, Select, SelectItem, Tag, TextArea,
} from '@carbon/react';
import { useRun } from '@/components/RunProvider';
import { Empty, Failed, Loading } from '@/components/States';
import { errorText, postDecision } from '@/lib/api';
import { labelFor } from '@/lib/labels';
import type { Control, Measure, Row } from '@/lib/types';

export default function Review() {
  const { result, loading, error, reload, reviewer } = useRun();
  const [recorded, setRecorded] = useState<Record<string, string>>({});

  const pending = useMemo(
    () => result?.surfaces.review.rows.filter((row) => row.controls.length > 0)
      ?? [], [result]);

  if (loading && !result) return <Loading label="Scoring the dataset." />;
  if (!result) return <Failed error={error} onRetry={reload} />;

  return (
    <section className="sea-section">
      <h2 className="sea-section__heading">Review</h2>
      <p className="sea-section__note">
        Each tile is one judgment covering every part it names, so it is
        confirmed once rather than once per part.
      </p>

      {/* THE SHARED CAVEAT, ONCE. */}
      <InlineNotification
        kind="info"
        lowContrast
        hideCloseButton
        title="Why these need a person"
        subtitle={
          'Correlated exposure can be defined as the same supplier, the same '
          + 'region, or the same tier, and the three give different answers. '
          + 'The arithmetic is deterministic once a definition is chosen, but '
          + 'the choice is not, so this system proposes and never decides. '
          + 'Grouping by supplier and grouping by region are not rivals: they '
          + 'answer different questions and both can be true at once.'
        }
      />

      {!reviewer.trim() && (
        <InlineNotification
          kind="warning"
          lowContrast
          hideCloseButton
          title="Add your name in the header first"
          subtitle="An anonymous decision is not a decision, so the log will refuse it."
        />
      )}

      {pending.length === 0 ? (
        <Empty title="Nothing is waiting for a judgment">
          No cluster in this run reaches the size at which a correlation exists
          at all. That is a finding about the data.
        </Empty>
      ) : (
        <div className="sea-review" style={{ marginTop: '1.5rem' }}>
          {pending.map((row) => (
            <Judgment
              key={row.key}
              row={row}
              runId={result.run.id}
              reviewer={reviewer}
              regionLabels={result.overview.region_labels}
              recorded={recorded[row.key]}
              onRecorded={(sentence) =>
                setRecorded((was) => ({ ...was, [row.key]: sentence }))}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function members(detail: Record<string, Measure>): string[] {
  const value = detail.members;
  return Array.isArray(value) ? value.map(String) : [];
}

function Judgment({ row, runId, reviewer, regionLabels, recorded, onRecorded }: {
  row: Row; runId: string; reviewer: string;
  regionLabels: Record<string, string>;
  recorded?: string; onRecorded: (sentence: string) => void;
}) {
  const [reason, setReason] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<unknown>(null);

  const list = members(row.detail);
  const basis = String(row.detail.basis ?? '');
  const codes = row.controls[0]?.reason_codes ?? [];

  useEffect(() => { setFailure(null); }, [reason, note]);

  async function act(control: Control) {
    setBusy(true);
    setFailure(null);
    try {
      const answer = await postDecision({
        run_id: runId, subject: control.subject, action: control.action,
        decided_by: reviewer, reason_code: reason, note,
      });
      onRecorded(answer.sentence);
    } catch (refused) {
      // THE REFUSAL TEXT IS THE ANSWER. The server says "an anonymous decision
      // is not a decision" or "'other' requires the note it promises", and
      // replacing that with "Could not save" throws away the instruction.
      setFailure(refused);
    } finally {
      setBusy(false);
    }
  }

  if (recorded) {
    return (
      <div className="sea-judgment">
        <InlineNotification
          kind="success"
          lowContrast
          hideCloseButton
          title="Recorded"
          subtitle={recorded}
        />
      </div>
    );
  }

  return (
    <div className="sea-judgment">
      <div className="sea-inline-tags">
        <Tag type="outline" size="sm">
          {basis === 'region' ? 'grouped by region' : 'grouped by supplier'}
        </Tag>
        <Tag type="warm-gray" size="sm">{list.length} parts covered</Tag>
        <Tag type="cool-gray" size="sm">a person decides this</Tag>
      </div>

      <h4 className="sea-chart__title" style={{ marginTop: '0.75rem' }}>
        {labelFor(row.key, regionLabels)}
      </h4>
      <p className="sea-judgment__claim">{row.sentence}</p>

      {failure !== null && (
        <InlineNotification
          kind="error"
          lowContrast
          title="Not recorded"
          subtitle={errorText(failure)}
          onClose={() => setFailure(null)}
        />
      )}

      <Select
        id={`reason-${row.key}`}
        labelText="Reason"
        helperText="Required to reject. Optional to confirm."
        value={reason}
        onChange={(event) => setReason(event.target.value)}
      >
        <SelectItem value="" text="— choose a reason —" />
        {codes.map((code) => (
          <SelectItem key={code} value={code} text={code} />
        ))}
      </Select>

      <div style={{ marginTop: '1rem' }}>
        <TextArea
          id={`note-${row.key}`}
          labelText="Note"
          helperText='Required when the reason is "other".'
          rows={2}
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
      </div>

      <div className="sea-judgment__actions">
        {row.controls.map((control) => (
          <Button
            key={control.action}
            kind={control.action === 'confirm' ? 'primary' : 'danger--tertiary'}
            size="md"
            disabled={busy}
            onClick={() => act(control)}
          >
            {control.action === 'confirm'
              ? `Confirm for ${control.member_count} parts`
              : 'Reject'}
          </Button>
        ))}
      </div>
    </div>
  );
}
