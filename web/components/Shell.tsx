'use client';
/**
 * The UI Shell: header, left rail, and the run context strip.
 *
 * THE WORDMARK IS SET, NOT DRAWN. Plex at 300 over 600, no logo: a mark nobody
 * commissioned looks worse than a well-set name. The weight break falls between
 * what the tool is about and what it is, which is the natural reading of the
 * name and needs no second colour to carry it.
 *
 * ONE ACCENT, and it is Carbon's. Every link, focus ring, primary button and
 * selected nav item is IBM Blue 60, supplied by the theme rather than typed
 * here. There is no second blue anywhere in this application.
 */
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Header, HeaderGlobalAction, HeaderGlobalBar, HeaderMenuButton,
  HeaderName, HeaderPanel, SideNav, SideNavItems, SideNavLink, SkipToContent,
  Tag, TextInput, Theme,
} from '@carbon/react';
import { Download, UserAvatar } from '@carbon/react/icons';
import { useState } from 'react';
import { PRODUCT_LEAD, PRODUCT_NAME, PRODUCT_TAIL } from '@/lib/labels';
import { useRun } from './RunProvider';
import { RunBar } from './RunBar';

const NAV = [
  { href: '/', label: 'Overview', hint: 'the shape of the whole set' },
  { href: '/exposure', label: 'Exposure', hint: 'what is worst' },
  { href: '/check', label: 'What to check', hint: 'what one fetch settles' },
  { href: '/review', label: 'Review', hint: 'judgments waiting for a person' },
  { href: '/decisions', label: 'Decision log', hint: 'who decided what' },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const [navOpen, setNavOpen] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const { result, reviewer, setReviewer } = useRun();

  // The count badge on Review, so pending work is visible from any surface.
  // A cluster is ONE judgment however many parts it covers, which is why this
  // counts rows and not members.
  const pending = result?.surfaces.review.rows.filter(
    (row) => row.controls.length > 0).length ?? 0;

  return (
    <Theme theme="g10">
      <Header aria-label={PRODUCT_NAME}>
        <SkipToContent />
        <HeaderMenuButton
          aria-label={navOpen ? 'Close menu' : 'Open menu'}
          isCollapsible
          onClick={() => setNavOpen((open) => !open)}
          isActive={navOpen}
        />
        <HeaderName href="/" prefix="">
          <span style={{ fontWeight: 300 }}>
            {PRODUCT_LEAD.replace(/ /g, '\u00a0')}&nbsp;
          </span>
          <span style={{ fontWeight: 600 }}>{PRODUCT_TAIL}</span>
        </HeaderName>
        <HeaderGlobalBar>
          <div style={{ display: 'flex', alignItems: 'center',
                        paddingInlineEnd: '0.5rem', width: '16rem' }}>
            <TextInput
              id="reviewer"
              labelText="Your name"
              hideLabel
              size="sm"
              placeholder="Your name, for the decision log"
              value={reviewer}
              onChange={(event) => setReviewer(event.target.value)}
            />
          </div>
          <HeaderGlobalAction
            aria-label="Export and run details"
            isActive={panelOpen}
            onClick={() => setPanelOpen((open) => !open)}
            tooltipAlignment="end"
          >
            <Download size={20} />
          </HeaderGlobalAction>
          <HeaderGlobalAction aria-label="Reviewer" tooltipAlignment="end">
            <UserAvatar size={20} />
          </HeaderGlobalAction>
        </HeaderGlobalBar>

        <HeaderPanel aria-label="Run details" expanded={panelOpen}>
          <RunPanel />
        </HeaderPanel>

        <SideNav
          aria-label="Surfaces"
          expanded={navOpen}
          isPersistent
          onOverlayClick={() => setNavOpen(false)}
        >
          <SideNavItems>
            {NAV.map((item) => (
              <SideNavLink
                key={item.href}
                as={Link}
                href={item.href}
                isActive={path === item.href}
                title={item.hint}
              >
                {/* A div rather than a span for the same reason the coverage
                    notes use one: Carbon's Tag is a div, and a div inside a
                    span is invalid HTML. */}
                <div style={{ display: 'flex', alignItems: 'center',
                              justifyContent: 'space-between', gap: '0.5rem',
                              width: '100%' }}>
                  {item.label}
                  {item.href === '/review' && pending > 0 && (
                    <Tag type="warm-gray" size="sm">{pending}</Tag>
                  )}
                </div>
              </SideNavLink>
            ))}
          </SideNavItems>
        </SideNav>
      </Header>

      {/* BELOW THE FIXED HEADER. Carbon's Header is position:fixed at 3rem
          tall and takes itself out of flow, so without this offset the run
          context strip renders underneath it and the first thing a reader
          looks for is the one thing they cannot see. */}
      <div className="sea-below-header">
        <RunBar />
        <main id="main-content" className="sea-main">{children}</main>
      </div>
    </Theme>
  );
}

function RunPanel() {
  const { result } = useRun();
  if (!result) return <div style={{ padding: '1rem' }}>No run loaded yet.</div>;
  return (
    <div style={{ padding: '1rem' }} className="sea-stack">
      <div>
        <div className="sea-runbar__label">Files read</div>
        {result.run.files.map((file) => (
          <div key={file.name} className="sea-runbar__value">
            {file.name} &middot; {file.bytes.toLocaleString()} bytes
          </div>
        ))}
      </div>
      <div>
        <div className="sea-runbar__label">Export</div>
        <div className="sea-runbar__value">
          Each table carries its own Export CSV in its toolbar.
        </div>
      </div>
    </div>
  );
}
