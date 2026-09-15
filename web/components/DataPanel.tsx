'use client';
/**
 * Data and coverage: where the figures came from, and what was not assessed.
 *
 * TWO THINGS IN ONE PLACE BECAUSE THEY ARE ONE QUESTION. "Which systems did
 * this read" and "what did it not cover" are both asked by a reader deciding
 * how much to trust the screen, and separating them puts half the answer
 * somewhere the other half is not.
 */
import { useState } from 'react';
import {
  Button, Modal, StructuredListBody, StructuredListCell, StructuredListHead,
  StructuredListRow, StructuredListWrapper, Tag,
} from '@carbon/react';
import { useRun } from './RunProvider';
import { UploadPanel } from './UploadPanel';

export function DataPanel() {
  const [open, setOpen] = useState(false);
  const { result } = useRun();

  return (
    <>
      <Button kind="ghost" size="sm" onClick={() => setOpen(true)}>
        Data and coverage
      </Button>
      <Modal
        open={open}
        onRequestClose={() => setOpen(false)}
        modalHeading="Data and coverage"
        modalLabel={result?.run.dataset ?? ''}
        passiveModal
        size="lg"
      >
        {!result ? <p>No run loaded yet.</p> : (
          <div className="sea-stack">
            <section>
              <h4 className="sea-chart__title">Where these figures came from</h4>
              <StructuredListWrapper isCondensed>
                <StructuredListHead>
                  <StructuredListRow head>
                    <StructuredListCell head>File</StructuredListCell>
                    <StructuredListCell head>System of record</StructuredListCell>
                    <StructuredListCell head>Pulled</StructuredListCell>
                    <StructuredListCell head>Digest</StructuredListCell>
                  </StructuredListRow>
                </StructuredListHead>
                <StructuredListBody>
                  {result.run.files.map((file) => {
                    const extract = result.extracts[file.name];
                    return (
                      <StructuredListRow key={file.name}>
                        <StructuredListCell noWrap>{file.name}</StructuredListCell>
                        <StructuredListCell>
                          {extract ? extract[0] : 'not in the extract manifest'}
                        </StructuredListCell>
                        <StructuredListCell>
                          {extract ? extract[1] : '—'}
                        </StructuredListCell>
                        <StructuredListCell noWrap>
                          <code>{file.sha256.slice(0, 12)}</code>
                        </StructuredListCell>
                      </StructuredListRow>
                    );
                  })}
                </StructuredListBody>
              </StructuredListWrapper>
              <p className="sea-section__note">
                The digest says which bytes were scored, so two runs of the same
                file name can be told apart. It detects a change; it does not
                prevent one.
              </p>
            </section>

            <section>
              <h4 className="sea-chart__title">What this run did not assess</h4>
              {/* A DIV RATHER THAN A P. Carbon renders `Tag` as a `div`, and a
                  div inside a p is invalid HTML that React resolves by moving
                  the node, which breaks hydration and silently reorders the
                  sentence. The class carries the typography either way. */}
              {result.surfaces.exposure.coverage?.notes.map((note) => (
                <div key={note.subject} className="sea-section__note">
                  <Tag type={note.kind === 'not_applicable'
                    ? 'cool-gray' : 'warm-gray'} size="sm">
                    {note.count}
                  </Tag>{' '}
                  {note.sentence}
                </div>
              ))}
            </section>

            <UploadPanel onDone={() => setOpen(false)} />
          </div>
        )}
      </Modal>
    </>
  );
}
