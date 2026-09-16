'use client';
/**
 * Loading, empty and failed, designed rather than defaulted.
 *
 * A BLANK PANEL IS A BUG REPORT THE READER HAS TO WRITE THEMSELVES. Each of
 * these says which of the three it is and what happens next, because the three
 * look identical when none of them is drawn.
 *
 * NO SKELETON, AND THAT IS A RULE RATHER THAN A TASTE. This file used to render
 * Carbon's `SkeletonText` and `SkeletonPlaceholder`, which resolve in the
 * browser to `animation: 3s ease-in-out infinite cds--skeleton` -- an endless
 * pulse on all six surfaces. DESIGN.md's Motion section forbids exactly that,
 * and says why: a page that animates while data settles implies the data is
 * moving, and it is not, it is a record. It also says what to do instead, which
 * is the whole of the replacement below: state it in words.
 */
import { Button, InlineNotification } from '@carbon/react';
import { errorFacts, errorText } from '@/lib/api';

export function Loading({ label }: { label: string }) {
  return (
    <section className="sea-section" aria-busy="true" aria-live="polite">
      <h2 className="sea-section__heading">{label}</h2>
      {/*
        STATED ONCE, NOT ESCALATED ON A TIMER. The hedge does the work a timer
        would: "can take up to a minute" and "if it has been idle" are both true
        at the first second of a three-second load and at the fortieth of a cold
        start, so there is no moment at which this sentence is wrong and nothing
        has to measure elapsed time to keep it honest.

        IT IS TRUE OF THE FREE PLAN ONLY. `render.yaml` carries the decision
        that put this deployment to sleep and names this sentence at the line
        that reverses it.
      */}
      <p className="sea-section__note">
        Rendering. This can take up to a minute if the scoring service has been
        idle: it sleeps when nothing is using it, and the first request after a
        quiet spell waits for it to start again. Nothing is wrong, and nothing
        needs clicking.
      </p>
    </section>
  );
}

export function Failed(
  { error, onRetry }: { error: unknown; onRetry?: () => void },
) {
  // The refusal text and its facts are joined into ONE string rather than
  // rendered as elements, because Carbon types `subtitle` as a string in this
  // version. Nothing is dropped to fit: every fact the server named is here.
  const facts = errorFacts(error);
  const subtitle = [errorText(error), ...facts].join(' ');
  return (
    <div>
      <InlineNotification
        kind="error"
        lowContrast
        hideCloseButton
        title="This did not load"
        subtitle={subtitle}
      />
      {onRetry && (
        <Button kind="tertiary" size="sm" onClick={onRetry}
                style={{ marginTop: '0.5rem' }}>
          Try again
        </Button>
      )}
    </div>
  );
}

/** Nothing to show, and why that is so. Never an empty panel. */
export function Empty({ title, children }: {
  title: string; children: React.ReactNode;
}) {
  return (
    <div style={{ padding: '2rem', background: 'var(--cds-layer-01)',
                  border: '1px dashed var(--cds-border-strong-01)' }}>
      <h4 className="sea-chart__title">{title}</h4>
      <p className="sea-section__note" style={{ marginBottom: 0 }}>{children}</p>
    </div>
  );
}

/** A threshold nobody has set. Points at the file and the key. */
export function NotConfigured({ what, key_ }: { what: string; key_: string }) {
  return (
    <InlineNotification
      kind="info"
      lowContrast
      hideCloseButton
      title={`${what} is not configured`}
      subtitle={`Set ${key_} in config/archetypes.yaml and re-score. There is no default: a threshold nobody set is a judgment attributed to nobody.`}
    />
  );
}
