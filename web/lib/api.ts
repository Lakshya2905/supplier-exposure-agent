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

/**
 * Where the scoring API is, from the browser's point of view.
 *
 * SAME ORIGIN BY DEFAULT, which means `app/api/[...path]/route.ts`: a
 * server-side proxy that holds the API key and resolves the backend address at
 * REQUEST time. That is the whole point. A static frontend ships its
 * environment to every visitor, so a key in `NEXT_PUBLIC_*` is not a key; and
 * `NEXT_PUBLIC_*` is inlined at BUILD time, so an address put there cannot be
 * changed without a redeploy.
 *
 * `NEXT_PUBLIC_API_BASE` survives as an ESCAPE HATCH for talking to a backend
 * directly — a developer pointing at a local uvicorn, or a deployment with no
 * credential to protect. It is no longer the mechanism, and nothing that needs
 * a secret goes down that path.
 */
const DIRECT_BASE = process.env.NEXT_PUBLIC_API_BASE;

export const API_BASE = DIRECT_BASE ?? '';

/** True when the browser is talking to the backend without the proxy. */
export const API_IS_DIRECT = Boolean(DIRECT_BASE);

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
    // ONLY REACHED WHEN THE PAGE ITSELF IS UNREACHABLE. Going through the proxy,
    // a backend that is down comes back as a 502 carrying the proxy's own
    // sentence, which knows the address it tried and whether anybody configured
    // one. This branch is the direct path, or this deployment being offline.
    throw new ApiError(
      API_IS_DIRECT
        ? `The scoring API did not answer at ${API_BASE}. Start it with `
          + '"uvicorn src.api.main:app --port 8000", or point '
          + 'NEXT_PUBLIC_API_BASE somewhere it is running.'
        : 'This page could not reach its own server. If it is deployed, the '
          + 'deployment is down; if it is local, restart "npm run dev".',
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
