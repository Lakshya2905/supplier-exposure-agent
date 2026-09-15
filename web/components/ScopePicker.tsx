'use client';
/**
 * Which criticality tiers this run assesses.
 *
 * A SET OF CHECKBOXES, NOT A SLIDER, and the control shape is the argument. A
 * slider is a cut-off, and a cut-off asserts that the tiers are ordered. They
 * may well be, in the company that maintains them, but that ordering is theirs
 * and this tool has not been told it: A above B above C is a convention, not a
 * fact, and a tool that assumed it would silently drop the tier somebody happens
 * to call Z for "safety critical".
 *
 * NOTHING CHECKED MEANS EVERYTHING, which is the honest default. A tool that
 * quietly scoped itself to somebody's idea of critical would report a clean
 * bill of health for a bill of materials it had mostly not read.
 */
import { useState } from 'react';
import { Button, Checkbox, Modal } from '@carbon/react';
import { useRun } from './RunProvider';

export function ScopePicker() {
  const { result, criticality, setCriticality } = useRun();
  const [open, setOpen] = useState(false);
  const [chosen, setChosen] = useState<string[]>(criticality);

  const labels = result ? Object.keys(result.scope.counts).sort() : [];
  const counts = result?.scope.counts ?? {};
  // EVERY PART UNCLASSIFIED IS THE CASE SOMEBODY ACTUALLY MEETS, not an empty
  // label list: `unclassified` is always a label, so a `labels.length === 0`
  // branch would never fire and the reader would be offered one checkbox with
  // no explanation of why there is only one.
  const noColumn = labels.length === 1 && labels[0] === 'unclassified';

  function toggle(label: string, on: boolean) {
    setChosen((was) => (on ? [...was, label]
                           : was.filter((entry) => entry !== label)));
  }

  return (
    <>
      <Button kind="ghost" size="sm" onClick={() => setOpen(true)}>
        {criticality.length ? `Scope: ${criticality.join(', ')}` : 'Scope'}
      </Button>
      <Modal
        open={open}
        onRequestClose={() => setOpen(false)}
        modalHeading="Which parts to assess"
        primaryButtonText="Re-score"
        secondaryButtonText="Cancel"
        onRequestSubmit={() => { setCriticality(chosen); setOpen(false); }}
        size="sm"
      >
        <p className="sea-section__note">
          Tick the criticality tiers to assess. Tick nothing to assess
          everything, which is what this run does now. Tiers are the ones your
          part master carries; this tool does not invent them and does not put
          them in an order.
        </p>
        <p className="sea-section__note">
          Parts left out are not examined and found fine. They are not examined,
          and the run says so.
        </p>
        {noColumn ? (
          <p className="sea-section__note">
            This extract carries no criticality column, so every part is
            unclassified and every part is assessed. Add a{' '}
            <code>criticality</code> column to <code>part_master.csv</code> and
            the tiers it contains will appear here.
          </p>
        ) : labels.map((label) => (
          <Checkbox
            key={label}
            id={`scope-${label}`}
            labelText={`${label} — ${counts[label].toLocaleString()} parts`}
            checked={chosen.includes(label)}
            onChange={(_event: unknown, { checked }: { checked: boolean }) =>
              toggle(label, checked)}
          />
        ))}
      </Modal>
    </>
  );
}
