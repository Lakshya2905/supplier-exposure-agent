'use client';
/**
 * Loading, empty and failed, designed rather than defaulted.
 *
 * A BLANK PANEL IS A BUG REPORT THE READER HAS TO WRITE THEMSELVES. Each of
 * these says which of the three it is and what happens next, because the three
 * look identical when none of them is drawn.
 *
 * THE SKELETONS ARE HERE BY A DECISION, NOT BY DEFAULT. They were removed on
 * 2026-09-16 because DESIGN.md's Motion section forbids a skeleton outright,
 * and `SkeletonText` and `SkeletonPlaceholder` do pulse: they resolve to
 * `animation: 3s ease-in-out infinite cds--skeleton`, injected by Carbon and
 * invisible to any scan of this repository's own stylesheets. They were
 * restored the same day, by the owner, on the record, because the v2 build
 * prompt asks for these two components by name for exactly this state.
 *
 * THE OBJECTION WAS NOT REFUTED, IT WAS OVERRULED, and DESIGN.md now records
 * that at the rule. A page that animates while data settles does imply the data
 * is moving, and it is a record rather than a process. What was weighed against
 * it is that a skeleton holds the shape of what is coming, so the layout does
 * not jump when it arrives.
 *
 * THE SENTENCE STAYS EITHER WAY, and it is the half that does the actual work
 * here: a skeleton says something is coming and cannot say it will be a minute.
 * See the note on it below.
 */
import {
  Button, InlineNotification, SkeletonPlaceholder, SkeletonText,
} from '@carbon/react';
import { errorFacts, errorText } from '@/lib/api';

export function Loading({ label }: { label: string }) {
  return (
    <section className="sea-section" aria-busy="true" aria-live="polite">
      <SkeletonText heading width="40%" />
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
      {/* The shape of what is coming, so the layout does not jump when it
          arrives. Three, because every surface that loads draws at least three
          charts. */}
      <div className="sea-charts">
        <SkeletonPlaceholder style={{ width: '100%', height: '12rem' }} />
        <SkeletonPlaceholder style={{ width: '100%', height: '12rem' }} />
        <SkeletonPlaceholder style={{ width: '100%', height: '12rem' }} />
      </div>
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
