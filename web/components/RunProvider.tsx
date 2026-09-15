'use client';
/**
 * One run, fetched once, shared by every surface.
 *
 * WHY A PROVIDER RATHER THAN A FETCH PER PAGE. Four surfaces are four views of
 * ONE scoring run, and the brief's point about the run context strip is that a
 * reader must always know which run they are looking at. Fetching per page
 * would let two surfaces show different runs after a re-score, and nothing on
 * screen would say so.
 */
import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
} from 'react';
import type { ReactNode } from 'react';
import { scoreDataset, scoreUpload } from '@/lib/api';
import type { ScoreResult } from '@/lib/types';

interface RunState {
  result: ScoreResult | null;
  loading: boolean;
  error: unknown;
  reload: () => void;
  loadDataset: (dataset: string) => Promise<void>;
  loadUpload: (files: File[], name: string) => Promise<void>;
  reviewer: string;
  setReviewer: (name: string) => void;
}

const Context = createContext<RunState | null>(null);

const REVIEWER_KEY = 'sea.reviewer';
const DEFAULT_DATASET = 'demo';

export function RunProvider({ children }: { children: ReactNode }) {
  const [result, setResult] = useState<ScoreResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  // THE REVIEWER'S NAME, ONCE. The Streamlit app asks for it on all four tabs,
  // which reads as four separate questions about the same thing. It lives in
  // the header here and is remembered per browser, never sent anywhere except
  // as the author of a decision the reviewer is making.
  const [reviewer, setReviewerState] = useState('');

  useEffect(() => {
    try {
      setReviewerState(window.localStorage.getItem(REVIEWER_KEY) ?? '');
    } catch { /* private window; the field simply starts empty */ }
  }, []);

  const setReviewer = useCallback((name: string) => {
    setReviewerState(name);
    try { window.localStorage.setItem(REVIEWER_KEY, name); } catch { /* ditto */ }
  }, []);

  const run = useCallback(async (work: () => Promise<ScoreResult>) => {
    setLoading(true);
    setError(null);
    try {
      setResult(await work());
    } catch (failure) {
      // The result is NOT cleared. A failed re-score leaves the previous run on
      // screen with the failure stated above it, because blanking the page
      // throws away work the reader was in the middle of reading.
      setError(failure);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadDataset = useCallback(
    (dataset: string) => run(() => scoreDataset(dataset)), [run]);
  const loadUpload = useCallback(
    (files: File[], name: string) => run(() => scoreUpload(files, name)),
    [run]);
  const reload = useCallback(() => { void loadDataset(DEFAULT_DATASET); },
                             [loadDataset]);

  useEffect(() => { void loadDataset(DEFAULT_DATASET); }, [loadDataset]);

  const value = useMemo<RunState>(() => ({
    result, loading, error, reload, loadDataset, loadUpload,
    reviewer, setReviewer,
  }), [result, loading, error, reload, loadDataset, loadUpload,
       reviewer, setReviewer]);

  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useRun(): RunState {
  const state = useContext(Context);
  if (!state) throw new Error('useRun outside RunProvider');
  return state;
}
