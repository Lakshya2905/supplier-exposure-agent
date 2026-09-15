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
import type { DecisionEvent, ScoreResult } from './types';

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';

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
    // NAMES THE ADDRESS IT TRIED. "Failed to fetch" sends somebody to the
    // browser console; the address plus the start command is the whole fix.
    throw new ApiError(
      `The scoring API did not answer at ${API_BASE}. Start it with ` +
      `"uvicorn src.api.main:app --port 8000", or set NEXT_PUBLIC_API_BASE ` +
      `to where it is running.`, 0, { cause: String(offline) });
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

export function scoreDataset(dataset: string): Promise<ScoreResult> {
  const body = new FormData();
  body.append('dataset', dataset);
  return request<ScoreResult>('/api/score', { method: 'POST', body });
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
