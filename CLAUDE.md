# Supplier Exposure Agent

Agent 3 of a multi-agent supply chain system. Answers: which single points of failure in a BOM would actually stop production, ranked by how badly. Full spec is in `docs/BRIEF.md`. Read it before proposing any plan.

## Commands

- Install: `pip install -e ".[dev]"`
- Test: `pytest -q`
- Generate data: `python -m src.generate_data --seed 42`
- Review UI: `streamlit run review_app.py`

## Working rules

- Synthetic data only. Never introduce real part numbers, real supplier names, scraped supplier data, or anything company-specific. If a realistic example is needed, generate it.
- Build in the order listed in the brief. Finish and commit one stage before starting the next. Do not scaffold stages 4 through 8 while stage 2 is in progress.
- Scoring dimensions stay separate. Do not collapse the five dimensions into one composite score, even if asked to "simplify the output".
- Scoring logic lives in plain Python functions with tests. Not in prompts. The autonomy claims have to be verifiable by reading code.
- Every ranked output carries its reasons. A number with no explanation is not a deliverable here.
- "I cannot tell" is a valid and required output. Missing lead times, incomplete supplier lists, and missing on-hand records must surface as unknown, never as a default value.
- Known gaps are marked `@pytest.mark.xfail(strict=True)` and listed in the README. Never delete a failing test to make CI green.
- The sourcing verdict is an explicit lookup table with one test per row. Never nested conditionals. The per-row tests hard-code their expected verdict by hand and must not import the table, or a wrong row would be wrong in both places and the tests would agree with the bug.
- `sourcing_list_status` gates the verdict only. It never enters scoring.
- `annual_spend_usd` is display-only and unscored. Ranking or weighting by it is the cost optimisation agent, not this one.
- A make part that also has suppliers is evaluated under both readings, stale-flag and genuine dual-mode. Agreement reports the verdict; disagreement goes to the exception lane, ordered by exposure under the worse reading. Do not pick a reading.
- Missing and zero are different facts. A blank on-hand means "no record" and must never be read as zero; a recorded zero is real. The same asymmetry governs demand: partially known usage yields an upper bound flagged incomplete, not an unknown.
- Eval floors are never produced by the generator under test.
- Where a judgment carries a threshold, the floors come from what the task
  requires and the threshold moves to meet them, never the reverse. If no
  threshold meets both floors, that is a finding, not a reason to lower one.
- Autonomy requires agreement on a settled answer. Agreement is necessary and
  not sufficient: two readings agreeing on an abstention is unanimous
  uncertainty, not a decision. Both parts must hold before anything executes,
  the readings agree AND what they agree on is an answer. A `readings_disagree`
  verdict therefore never executes, however the readings compared.
- Every measure keeps its unit. A dimension expressed as a unitless number in a
  fixed range is a composite already assembled, whichever way it is displayed.
  Refusing to sum is not sufficient; refusing to normalise is.
- Absence is not zero, and a bound is not an abstention. Where incompleteness is
  reported to more than one consumer, report the fact of it and let each
  consumer name the bound direction, because the safe direction is not constant.
- Two kinds of disagreement, distinguished by one test: could any fact settle
  it. Settleable disagreement is uncertainty and routes to a lane. Unsettleable
  disagreement is structure and is reported as a finding. Routing a
  complementary disagreement buries a real result among things that look like
  errors.
- Any default ordering must be arbitrary AND stable. Insertion order and dict
  order are arbitrary today and silently become meaningful when an upstream
  function changes how it iterates. Sort by an explicit key and label the order
  in the output, because a plausible default is read as a ranking.
- Never impute a missing value in order to rank something. Evaluate the actual
  conditions with the field unknown. A list ordered by a guessed value is a
  forecast wearing a work queue's clothes.
- Autonomy is an affordance, never an appearance. An executed finding has
  nothing to click; a recommends finding has a control. A styling distinction is
  one commit from evaporating, so the model refuses to construct an executed row
  carrying a control.
- Visual encodings are nominal only. Hue may distinguish categories; intensity,
  size, length and fill fraction may not, because an ordinal encoding of a
  heterogeneous set is a composite drawn rather than computed. Strip every
  colour and no information may be lost.
- Every executed finding carries reachable, read-only evidence. A conclusion a
  reviewer cannot check is one they must trust, and trust is what this system
  replaces with verification.
- Default flow for any change: branch, push the branch, open a PR, merge when
  the gate is green. This is not a preference, it is the only path that works:
  main requires the `gate` status check and enforce_admins is on, so a push
  carrying a fresh commit has no green check yet and GitHub refuses it. The
  local gate still runs before every commit; CI is the second opinion, not a
  replacement.
- Run `python eval_harness.py` before every commit. A task is not done unless
  SHIP GATE: PASS. It blocks on a failing test, a PASSING xfail, a manifest
  mismatch, or a missed floor. Never lower a floor to pass: each carries its
  derivation and what would have to be true for it to be wrong, so changing one
  edits its justification in the same commit.
- evals/ is frozen and never regenerated by the gate. eval_build.py is the only
  file allowed to import the generator, and a test asserts the harness cannot
  reach it even transitively.
- Store structured, render prose, never store the prose. The decision log holds
  no rendered text; `render(event)` produces it on demand and golden files pin
  the wording. `evals/` and `tests/fixtures/` are committed and frozen; `data/` is gitignored and regenerated from a documented seed.
- The fixture BOM is hand-authored, never generated. A fixture the generator produced would be the generator grading its own homework.
- Governance is option 2 from the brief: a thin placeholder interface. Option 1 is unavailable, verified. The placeholder copies agent 1's reason-code vocabulary and decision-log record shape verbatim, and is not deepened otherwise. Extraction into a shared package waits until after this agent ships.

## Autonomy levels (these are the product, not a detail)

- Explosion, joining, exposure identification: executes automatically.
- Correlation and concentration flagging: recommends, human confirms.
- Recommended actions: recommends permanently, never auto-selects.
- Supplier qualification: never. Out of scope by design.

## Out of scope

Cost optimisation, supplier scorecarding, negotiation support, resourcing workflow. If a change starts pulling in one of these, stop and say so instead of building it.

## Design System

Always read DESIGN.md before making any visual or UI decision.
Fonts, colours, spacing, the chip vocabulary, the absence states, the evidence
anatomy, and the anti-ranking contract are all defined there.
Do not deviate without explicit user approval.
In QA mode, flag any code that does not match DESIGN.md.

Two rules from it are correctness constraints, not preferences:
- Never state a perceptual guarantee in HSL. Use OKLCH or CIELAB and assert the
  measured property, not the notation.
- Absence is never dimmed, never zero, never blank. It renders at the same weight
  and footprint as an asserted value.
