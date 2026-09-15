'use client';
/**
 * The three kinds of unknown, each with its own treatment.
 *
 * THEY ARE NOT INTERCHANGEABLE AND THE READER MUST NOT COLLAPSE THEM. A part
 * whose supplier list is unresolved could be settled by somebody making a phone
 * call. A part the question does not attach to cannot be settled by anybody,
 * ever. A threshold nobody has configured is settled by editing a file. Three
 * different instructions, and one grey "n/a" for all three would tell a reader
 * to do nothing in the two cases where there is something to do.
 *
 * NEVER ZERO, NEVER BLANK, NEVER A DASH. A gap in a table invites a reader to
 * substitute zero, and zero is both a real measurement and the worst one.
 */
import { Tag } from '@carbon/react';
import type { Completeness } from '@/lib/types';

/** Something could be established and has not been. Somebody can fetch it. */
export function Unresolved({ children }: { children?: React.ReactNode }) {
  return (
    <Tag type="warm-gray" size="sm" title="Not enough data to say. Somebody can fetch this.">
      {children ?? 'not enough data to say'}
    </Tag>
  );
}

/** The question does not attach to this part. Nobody can fetch anything. */
export function NotApplicable({ children }: { children?: React.ReactNode }) {
  return (
    <Tag type="cool-gray" size="sm" title="The question does not attach to this part.">
      {children ?? 'does not apply here'}
    </Tag>
  );
}

/** Settled, and the worst this measure can say without a threshold. */
export function NoPath({ children }: { children?: React.ReactNode }) {
  return (
    <Tag type="red" size="sm" title="Checked, and there is nothing there.">
      {children ?? 'nothing there'}
    </Tag>
  );
}

const BOUND_WORDS: Partial<Record<Completeness, string>> = {
  // A bound rendered as a bare number is a lie by omission: "11 days" reads as
  // a measurement when the true figure could be anything below it.
  upper_bound: 'at most',
  lower_bound: 'at least',
};

export function boundPrefix(completeness: Completeness): string {
  return BOUND_WORDS[completeness] ?? '';
}

/**
 * One measure, rendered with its completeness. The single place a UI decides
 * how an absent value looks, so it cannot be decided differently on one screen.
 */
export function MeasureText(
  { value, completeness }: { value: string | null; completeness: Completeness },
) {
  if (completeness === 'cannot_tell') return <Unresolved />;
  if (completeness === 'not_applicable') return <NotApplicable />;
  if (completeness === 'no_recovery_path') return <NoPath>no supplier on file</NoPath>;
  if (value === null) return <Unresolved />;
  const prefix = boundPrefix(completeness);
  return (
    <span className="sea-figure">
      {prefix && <span style={{ color: 'var(--cds-text-secondary)' }}>{prefix} </span>}
      {value}
    </span>
  );
}
