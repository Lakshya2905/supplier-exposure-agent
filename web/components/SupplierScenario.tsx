'use client';
/**
 * If this supplier stopped: what stops, is there a backup, how long to fix it.
 *
 * THE PATHS ARE LISTED AND NEVER ORDERED BY DURATION. `src/scenario.py` returns
 * them in a fixed sequence -- hold, then switch, then qualify -- and this
 * renders that sequence. Sorting them by days here would put the choosing back
 * in, on the one surface where a reader is most likely to take the top row as
 * the answer.
 *
 * HOLDING STOCK IS NOT A FIX and its own label says so. It is rendered with the
 * others because a reader deciding between switching and qualifying needs to
 * know how long they have, and separating it would make that a second lookup.
 *
 * PARTS THAT SURVIVE ARE COUNTED, NOT LISTED. A supplier stopping leaves most
 * of its parts with other sources, and listing all of them would bury the two
 * that stop. The count is stated so nobody has to wonder whether they were
 * checked.
 */
import { Tag } from '@carbon/react';
import { formatDays } from '@/lib/measure';
import { OUTCOME, OUTCOME_CLAUSE } from '@/lib/labels';
import type { Affected, ScenarioPath } from '@/lib/types';

/** A duration, with its absence stated rather than blanked.
 *
 *  NOT A DASH AND NOT A BLANK. "Nobody has timed this" is a finding about the
 *  data and renders at the same weight as a number. */
function days(path: ScenarioPath): string {
  if (path.completeness === 'cannot_tell') return 'nobody has timed this';
  const text = formatDays(path.days);
  if (text === null) return 'nobody has timed this';
  const prefix = path.completeness === 'lower_bound' ? 'at least ' : '';
  const suffix = path.completeness === 'upper_bound' ? ' at most' : '';
  return `${prefix}${text}${suffix}`;
}

const LISTED = ['stops', 'sole_sourced', 'unsettled'];

export function SupplierScenario(
  { supplier, affected, order }: {
    supplier: string; affected: Affected[]; order: string;
  },
) {
  if (!affected.length) {
    return (
      <p className="sea-section__note">
        Nothing in this run names {supplier} as a source, so there is nothing
        to lose.
      </p>
    );
  }

  const counts = affected.reduce<Record<string, number>>((tally, row) => {
    tally[row.outcome] = (tally[row.outcome] ?? 0) + 1;
    return tally;
  }, {});
  const listed = affected.filter((row) => LISTED.includes(row.outcome));
  const survive = affected.length - listed.length;

  return (
    <div>
      <p className="sea-section__note">
        <strong>If {supplier} stopped.</strong>{' '}
        {Object.entries(counts)
          .filter(([outcome]) => outcome !== 'still_multi')
          .map(([outcome, n]) => `${n} ${OUTCOME_CLAUSE[
            outcome as keyof typeof OUTCOME_CLAUSE]}`)
          .join('; ')}
        {survive > 0 && `; ${survive} would still have other sources`}. {order}
      </p>

      {listed.map((row) => (
        <div key={row.part_number} className="sea-scenario__part">
          {/* A DIV, NOT A P. Carbon's Tag renders a div, and a div inside a p
              is invalid HTML that React reports as a hydration error. This
              repository has hit it before -- `app/page.tsx` carries the same
              note over the coverage tags -- and it came back here because the
              element that breaks it is three components away from the rule. */}
          <div className="sea-section__note" style={{ marginBottom: '0.25rem' }}>
            <strong>{row.part_number}</strong>{' '}
            <Tag type="cool-gray" size="sm">{OUTCOME[row.outcome]}</Tag>{' '}
            {row.suppliers_remaining === 0
              ? 'No other supplier is on this part.'
              : `${row.suppliers_remaining} other supplier`
                + `${row.suppliers_remaining === 1 ? ' is' : 's are'} on this `
                + `part, of which ${row.remaining_can_quote} `
                + `${row.remaining_can_quote === 1 ? 'has' : 'have'} a lead `
                + 'time on file.'}
          </div>
          <ul className="sea-scenario__paths">
            {row.paths.map((path) => (
              <li key={path.kind}>
                {path.label} — <strong>{days(path)}</strong>
              </li>
            ))}
          </ul>
        </div>
      ))}

      {listed.length === 0 && (
        <p className="sea-section__note">
          Every part this supplier touches has another source, so nothing here
          stops or drops to one source.
        </p>
      )}
    </div>
  );
}
