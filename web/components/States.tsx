'use client';
/**
 * Loading, empty and failed, designed rather than defaulted.
 *
 * A BLANK PANEL IS A BUG REPORT THE READER HAS TO WRITE THEMSELVES. Each of
 * these says which of the three it is and what happens next, because the three
 * look identical when none of them is drawn.
 */
import {
  Button, InlineNotification, SkeletonPlaceholder, SkeletonText,
} from '@carbon/react';
import { errorFacts, errorText } from '@/lib/api';

export function Loading({ label }: { label: string }) {
  return (
    <section className="sea-section" aria-busy="true" aria-live="polite">
      <SkeletonText heading width="40%" />
      <p className="sea-section__note">{label}</p>
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
