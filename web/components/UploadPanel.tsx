'use client';
/**
 * Scoring somebody else's data, without touching the repository.
 *
 * THE VALIDATION MESSAGE IS THE FEATURE. An enterprise running this on their
 * own extract will get it wrong the first time, and what decides whether they
 * try again is whether the tool names the file and the column or says "invalid
 * input". The API answers with the missing file names; this renders them, and
 * never rewrites them into something friendlier that says less.
 */
import { useState } from 'react';
import {
  Button, FileUploader, InlineNotification, TextInput, UnorderedList,
  ListItem,
} from '@carbon/react';
import { errorFacts, errorText } from '@/lib/api';
import { useRun } from './RunProvider';

const REQUIRED = ['bom.csv', 'part_master.csv', 'demand_plan.csv',
                  'suppliers.csv', 'lead_times.csv', 'sources.csv'];
const OPTIONAL = ['recovery_inputs.csv'];

export function UploadPanel({ onDone }: { onDone?: () => void }) {
  const { loadUpload } = useRun();
  const [files, setFiles] = useState<File[]>([]);
  const [name, setName] = useState('');
  const [failure, setFailure] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setFailure(null);
    try {
      await loadUpload(files, name.trim() || 'uploaded extract');
      onDone?.();
    } catch (problem) {
      setFailure(problem);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <h4 className="sea-chart__title">Score your own extract</h4>
      <p className="sea-section__note">
        Six files are required and one is optional. Headers must match the data
        dictionary exactly; nothing is inferred and no column is coerced, so a
        mismatch is refused with the file and the column named rather than
        scored into a wrong answer.
      </p>
      <UnorderedList style={{ marginBottom: '1rem' }}>
        <ListItem>Required: {REQUIRED.join(', ')}</ListItem>
        <ListItem>Optional: {OPTIONAL.join(', ')}</ListItem>
      </UnorderedList>

      {failure !== null && (
        <InlineNotification
          kind="error"
          lowContrast
          title="That extract was not scored"
          subtitle={[errorText(failure), ...errorFacts(failure)].join(' ')}
          onClose={() => setFailure(null)}
        />
      )}

      <TextInput
        id="dataset-name"
        labelText="Name this extract"
        helperText="Shown in the run strip and stored with the run."
        placeholder="e.g. ERP extract, March"
        value={name}
        onChange={(event) => setName(event.target.value)}
      />
      <div style={{ marginTop: '1rem' }}>
        <FileUploader
          accept={['.csv']}
          buttonKind="tertiary"
          buttonLabel="Add files"
          filenameStatus="edit"
          labelDescription="CSV only. Select all of them at once."
          labelTitle="Input files"
          multiple
          onChange={(event) => {
            const chosen = (event.target as HTMLInputElement).files;
            setFiles(chosen ? Array.from(chosen) : []);
          }}
        />
      </div>
      <Button
        kind="primary"
        disabled={files.length === 0 || busy}
        onClick={submit}
        style={{ marginTop: '1rem' }}
      >
        {busy ? 'Scoring' : `Score ${files.length} file(s)`}
      </Button>
    </section>
  );
}
