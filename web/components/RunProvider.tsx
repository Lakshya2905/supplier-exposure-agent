'use client';
/**
 * One run, fetched once, shared by every surface.
 *
 * WHY A PROVIDER RATHER THAN A FETCH PER PAGE. Four surfaces are four views of
 * ONE scoring run, and the brief's point about the run context strip is that a
 * reader must always know which run they are looking at. Fetching per page
 * would let two surfaces show different runs after a re-score, and nothing on
 * screen would say so.
 *
 * AND IT HOLDS HOW THAT RUN WAS OBTAINED, which is the other half of the same
 * promise. Until 2026-10-28 it did not: `reload` and `setCriticality` both
 * named the demo dataset outright, so Re-score, the scope picker and every
 * "Try again" button swapped an uploaded extract for the synthetic one and
 * applied the reader's own filter to it. Measured, on the day it was fixed:
 * upload an extract, narrow the scope to one tier, and the screen read
 * "Parts scored: 0" over demo data — an empty result that looks exactly like
 * good news. `ScopePicker` states the distinction this destroyed: parts left
 * out "are not examined and found fine. They are not examined."
 */
import {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
} from 'react';
import type { ReactNode } from 'react';
import { scoreDataset, scoreUpload } from '@/lib/api';
import type { ScoreResult } from '@/lib/types';

/**
 * What the run on screen was scored from, kept so that scoring it again means
 * scoring the same thing again.
 *
 * AN UPLOAD KEEPS ITS `File` HANDLES rather than a run id, because a re-score
 * is a new run of the same bytes and the browser already has them. The handles
 * are the operating system's: a file edited or moved since it was chosen will
 * fail to read, and that failure is reported rather than papered over.
 */
type Source =
  | { kind: 'dataset'; dataset: string }
  | { kind: 'upload'; files: File[]; name: string };

interface RunState {
  result: ScoreResult | null;
  loading: boolean;
  error: unknown;
  reload: () => void;
  loadDataset: (dataset: string) => Promise<void>;
  loadUpload: (files: File[], name: string) => Promise<void>;
  reviewer: string;
  setReviewer: (name: string) => void;
  /** Criticality labels this run assessed. Empty means everything, which is
   *  the honest default: a tool that quietly scoped itself would report a
   *  clean result for a bill of materials it had mostly not read. */
  criticality: string[];
  setCriticality: (labels: string[]) => void;
}

const Context = createContext<RunState | null>(null);

const REVIEWER_KEY = 'sea.reviewer';
const DEFAULT_SOURCE: Source = { kind: 'dataset', dataset: 'demo' };

export function RunProvider({ children }: { children: ReactNode }) {
  const [result, setResult] = useState<ScoreResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  // THE REVIEWER'S NAME, ONCE. The Streamlit app asks for it on all four tabs,
  // which reads as four separate questions about the same thing. It lives in
  // the header here and is remembered per browser, never sent anywhere except
  // as the author of a decision the reviewer is making.
  const [reviewer, setReviewerState] = useState('');
  const [criticality, setCriticalityState] = useState<string[]>([]);
  const [source, setSource] = useState<Source>(DEFAULT_SOURCE);

  useEffect(() => {
    try {
      setReviewerState(window.localStorage.getItem(REVIEWER_KEY) ?? '');
    } catch { /* private window; the field simply starts empty */ }
  }, []);

  const setReviewer = useCallback((name: string) => {
    setReviewerState(name);
    try { window.localStorage.setItem(REVIEWER_KEY, name); } catch { /* ditto */ }
  }, []);

  /**
   * Score something and adopt it as the run on screen.
   *
   * THIS ONE THROWS, AND THAT IS THE DECISION. Where a failure belongs is not
   * one question but two, and they have different answers: a re-score nobody
   * is standing in front of belongs on the page beside the run it failed to
   * replace, while a refused extract belongs in the panel the reader is
   * working in, next to the files they are about to correct. Catching here
   * answered both with the first, which made the second unreachable —
   * `UploadPanel`'s refusal notification had never rendered once, and its
   * modal closed on a 422 as though the upload had worked.
   *
   * So the swallow moved out to `refresh`, and the one caller who is waiting
   * for an answer gets one.
   */
  const score = useCallback(async (next: Source, labels: string[]) => {
    setLoading(true);
    setError(null);
    try {
      const scored = next.kind === 'dataset'
        ? await scoreDataset(next.dataset, labels)
        : await scoreUpload(next.files, next.name, labels);
      // ALL THREE DESCRIBE THE RUN ON SCREEN, so all three move together and
      // only once it is on screen. A refused extract must not become what the
      // next Re-score retries, and must not leave the scope control reporting
      // a scope this run was never scored at.
      setResult(scored);
      setSource(next);
      setCriticalityState(labels);
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * A re-score with nobody waiting on it: the page carries the failure.
   *
   * The result is NOT cleared. A failed re-score leaves the previous run on
   * screen with the failure stated above it, because blanking the page throws
   * away work the reader was in the middle of reading.
   */
  const refresh = useCallback(
    (next: Source, labels: string[]) => score(next, labels).catch(setError),
    [score]);

  const loadDataset = useCallback(
    (dataset: string) => refresh({ kind: 'dataset', dataset }, criticality),
    [refresh, criticality]);

  // AN UPLOAD ARRIVES UNSCOPED. Criticality tiers belong to the part master
  // that declares them, so carrying the last dataset's tiers over would score
  // somebody's extract against labels it may not contain, and a scope that
  // matches nothing looks exactly like a clean bill of health.
  //
  // NOT `refresh`: this is the path with somebody waiting on the other end.
  const loadUpload = useCallback(
    (files: File[], name: string) => score({ kind: 'upload', files, name }, []),
    [score]);

  const reload = useCallback(() => { void refresh(source, criticality); },
                             [refresh, source, criticality]);

  const setCriticality = useCallback((labels: string[]) => {
    void refresh(source, labels);
  }, [refresh, source]);

  // ONCE, ON MOUNT, and `refresh` is stable so it stays once. It used to
  // depend on `loadDataset`, which changes identity with the scope, so one
  // trip through the scope picker scored the dataset twice: the explicit
  // re-score and then this effect, firing again on the new identity.
  useEffect(() => { void refresh(DEFAULT_SOURCE, []); }, [refresh]);

  const value = useMemo<RunState>(() => ({
    result, loading, error, reload, loadDataset, loadUpload,
    reviewer, setReviewer, criticality, setCriticality,
  }), [result, loading, error, reload, loadDataset, loadUpload,
       reviewer, setReviewer, criticality, setCriticality]);

  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useRun(): RunState {
  const state = useContext(Context);
  if (!state) throw new Error('useRun outside RunProvider');
  return state;
}
