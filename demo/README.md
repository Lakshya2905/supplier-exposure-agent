# Demo dataset: committed for display only

Generated from seed 42 by the documented command:

    python -m src.generate_data --seed 42 --out-dir demo

It exists for one reason. A cold container on Streamlit Community Cloud cannot
regenerate data during its first page load, and idle apps are put to sleep, so
without a committed dataset a visitor arriving at a sleeping app would find a
blank screen.

**This directory is never read by the eval harness or by any test.** A dataset
that exists to be looked at must not also be a thing correctness is judged
against, and the two roles would quietly merge the first time somebody found it
convenient. `tests/test_demo_dataset.py` asserts the separation, and checks the
shape of this directory rather than its contents so that the tests themselves do
not become a reader of it.

There is deliberately no answer key here. Correctness is measured against
`evals/`, which is frozen under a manifest and gated in CI.

| directory | rule |
|---|---|
| `evals/` | frozen, gated, never regenerated |
| `data/` | gitignored, regenerated from the seed |
| `demo/` | committed, display only, never an input to correctness |
