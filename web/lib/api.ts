/**
 * Talking to the scoring API.
 *
 * ERRORS ARE CARRIED, NEVER SWALLOWED. The API answers a refusal with the
 * sentence that says what to do differently: "an anonymous decision is not a
 * decision", "required files are missing from the upload" with the file named.
 * A `catch` that replaces those with "Something went wrong" throws away the
 * only useful part of the response, so `ApiError` keeps the detail and the
 * components render it.
 */
import type { Comparison, DecisionEvent, ScoreResult } from './types';

const CONFIGURED_BASE = process.env.NEXT_PUBLIC_API_BASE;

export const API_BASE = CONFIGURED_BASE ?? 'http://127.0.0.1:8000';

/**
 * Whether this build was given an API address at all.
 *
 * `NEXT_PUBLIC_*` IS INLINED AT BUILD TIME, not read at runtime, so a variable
 * added to a host's settings after the build has no effect until something
 * redeploys. That is the single most confusing thing about deploying this: the
 * setting is visibly correct in the dashboard and the page is visibly still
 * wrong, and nothing connects the two.
 */
export const API_IS_CONFIGURED = Boolean(CONFIGURED_BASE);

/** Whether the page itself is being served from somebody's own machine. */
function servedLocally() {
  if (typeof window === 'undefined') return true;
  return ['localhost', '127.0.0.1', '0.0.0.0'].includes(
    window.location.hostname);
}

export class ApiError extends Error {
  detail: unknown;
  status: number;
  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

/** The human-readable half of a refusal, whatever shape it arrived in. */
export function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    const detail = error.detail as Record<string, unknown> | string | undefined;
    if (typeof detail === 'string') return detail;
    if (detail && typeof detail === 'object' && 'error' in detail) {
      return String(detail.error);
    }
    return error.message;
  }
  return error instanceof Error ? error.message : String(error);
}

/** Extra lines a refusal carries: the files missing, the datasets that exist. */
export function errorFacts(error: unknown): string[] {
  if (!(error instanceof ApiError)) return [];
  const detail = error.detail as Record<string, unknown> | undefined;
  if (!detail || typeof detail !== 'object') return [];
  return Object.entries(detail)
    .filter(([key, value]) => key !== 'error' && Array.isArray(value))
    .map(([key, value]) =>
      `${key.replace(/_/g, ' ')}: ${(value as unknown[]).join(', ')}`);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch (offline) {
    // NAMES THE ADDRESS IT TRIED, AND SAYS WHOSE MACHINE THAT IS. The same
    // failure has two completely different causes and the wrong advice is
    // useless in both directions.
    //
    // On a developer's machine, `127.0.0.1:8000` is their backend and the fix
    // is to start it. On a DEPLOYED page, `127.0.0.1` is the VISITOR'S machine:
    // the browser is loyally trying to reach a server on the laptop of whoever
    // opened the link. Telling them to run uvicorn is advice for somebody else.
    // That case means the build never received NEXT_PUBLIC_API_BASE, and
    // because it is inlined at build time, setting it now is not enough.
    const deployedWithoutBackend = !API_IS_CONFIGURED && !servedLocally();
    throw new ApiError(
      deployedWithoutBackend
        ? 'This deployment was built without NEXT_PUBLIC_API_BASE, so the page '
          + `is trying to reach a scoring API at ${API_BASE} — which is your `
          + 'own machine, not the server. Set NEXT_PUBLIC_API_BASE to where '
          + 'the backend is running and redeploy: the value is baked in at '
          + 'build time, so saving it without a redeploy changes nothing.'
        : `The scoring API did not answer at ${API_BASE}. Start it with `
          + '"uvicorn src.api.main:app --port 8000", or set '
          + 'NEXT_PUBLIC_API_BASE to where it is running.',
      0, { cause: String(offline) });
  }
  if (!response.ok) {
    let detail: unknown = await response.text();
    try { detail = JSON.parse(detail as string); } catch { /* text it is */ }
    if (detail && typeof detail === 'object' && 'detail' in detail) {
      detail = (detail as { detail: unknown }).detail;
    }
    throw new ApiError(`${path} answered ${response.status}`,
                       response.status, detail);
  }
  return response.json() as Promise<T>;
}

export function scoreDataset(dataset: string,
                             criticality?: string[]): Promise<ScoreResult> {
  const body = new FormData();
  body.append('dataset', dataset);
  // A SET OF LABELS, never a cut-off. Omitted entirely when nothing was chosen,
  // because an empty parameter is somebody who left the box alone and scoring
  // nothing at all is never what they meant.
  if (criticality && criticality.length) {
    body.append('criticality', criticality.join(','));
  }
  return request<ScoreResult>('/api/score', { method: 'POST', body });
}

export function fetchChanges(before: string, after: string): Promise<Comparison> {
  return request<Comparison>(
    `/api/changes?before=${encodeURIComponent(before)}`
    + `&after=${encodeURIComponent(after)}`);
}

export function fetchRuns(): Promise<{ runs: Array<{
  id: string; created_at: string; dataset: string;
}> }> {
  return request('/api/runs');
}

export function scoreUpload(files: File[], name: string): Promise<ScoreResult> {
  const body = new FormData();
  files.forEach((file) => body.append('files', file, file.name));
  body.append('dataset', name);
  return request<ScoreResult>('/api/score', { method: 'POST', body });
}

export function fetchRun(id: string): Promise<ScoreResult> {
  return request<ScoreResult>(`/api/run/${id}`);
}

export function fetchDecisions(): Promise<{
  decisions: DecisionEvent[]; reason_codes: string[];
}> {
  return request('/api/decisions');
}

export function postDecision(body: {
  run_id: string; subject: string; action: string;
  decided_by: string; reason_code?: string; note?: string;
}): Promise<{ decision: DecisionEvent; sentence: string }> {
  return request('/api/decisions', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
}
