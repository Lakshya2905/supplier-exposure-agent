# Supplier Exposure Agent: Build Brief (v2)

Context handoff for building this in Claude Code. This is my own project, agent 3 of a multi-agent supply chain system where each agent carries an explicit autonomy level. Build generic, on synthetic data. No company-specific data, no scraped supplier information, no real part numbers. It has to stand alone as portfolio work regardless of who ever sees it.

**Time box: one week.** This is a focused extension, not a new system. If it grows past that, cut scope rather than extending the deadline.

Changes from v1: demand input added so buffer cover is computable, known-gap tests specified as xfail strict so CI stays meaningful, governance reuse specified as a package dependency rather than a vague instruction to factor out.

---

## The problem

A hardware manufacturer buys hundreds or thousands of parts to build a finished product. Somewhere in that bill of materials are parts with exactly one qualified supplier. If that supplier misses, the line stops, and nothing else in inventory can compensate.

Most companies know this in the abstract and cannot answer it precisely. The information is spread across a BOM, a supplier master, and a lead time table that nobody joins together. So the exposure gets discovered when the supplier fails, not before.

The agent answers one question: which single points of failure in this BOM would actually stop production, ranked by how badly.

---

## Why this problem and not another

- It is real for any hardware manufacturer, so it is portfolio work independent of any company.
- It extends existing work rather than starting from zero. JetStream Supply already does BOM explosion, lead-time offsets, and reorder policy evaluation.
- It has a clean autonomy story: identifying exposure is safe to automate, recommending a second source is not, qualifying a supplier never is.

---

## Inputs (synthetic, generated)

**BOM:** multi-level, at least 3 levels deep, 200 to 400 parts. Parent-child relationships with quantity per assembly. Include some parts used in multiple assemblies (common parts) because those change the risk math.

**Supplier master:** part number, qualified supplier(s), supplier region, qualification date. Most parts have 2 or 3 qualified suppliers, a meaningful minority have exactly 1.

**Lead time table:** part number, supplier, quoted lead time in days, historical variance. Long-lead parts should range from a few days to 40+ weeks so the tail actually matters.

**Part master:** part number, description, `source_type`, `sourcing_list_status`, on-hand inventory, tooling ownership flag, annual spend.

- `source_type` is **required and never blank**, one of `make` or `buy`. It separates two cases that otherwise collapse into one: zero supplier rows on a `make` part is a known fact, zero supplier rows on a `buy` part is a genuine unknown. Without this column the data cannot tell them apart and the system would have to guess.
- `sourcing_list_status` is one of `verified`, `unverified`, or blank, covering lists that exist but are unconfirmed. An unverified list of one may really be a list of two, so it is not the same claim as a verified list of one.
- On-hand is optional in the sense that some parts legitimately have no record. A missing on-hand must produce "cannot tell" for buffer cover on that part, **not a zero**. A recorded zero and a missing record are different facts and are encoded differently.
- Tooling ownership (company-owned or supplier-owned) determines how portable the part is. It may be blank, which makes portability unknown.
- `annual_spend_usd` is a **display-only pass-through column, never scored, ranked, or weighted.** It is the first thing a sourcing manager's eye goes to and it costs one column. The moment anyone wants to rank by it, that is the cost optimisation agent, which is out of scope.

Minimum order quantity is **not** collected. Nothing consumes it, and buffer-build costing belongs to the cost optimisation agent.

**Demand plan:** finished good, annual units. Required, not optional. Buffer cover is on-hand divided by a consumption rate, and consumption rate does not exist without a demand figure. Part-level consumption is derived: annual usage of a part equals the sum over finished goods of (exploded quantity per finished good x annual units).

Four finished goods with **spread annual volumes**, roughly 12000 / 4500 / 900 / 300. The spread is the load-bearing part, not the count. Buffer cover is measured in days, so a part shared between a high runner and a low runner has its exposure set almost entirely by the high runner, and a flat demand plan hides that completely.

One finished good is **absent from the demand plan**, and it shares at least three parts with the others. That produces two distinct cases, both of which must exist in the data:

- **Partially known usage.** A part fed by three recorded finished goods and one absent one. Usage is neither known nor unknown, and the correct output is a **bound, not a shrug**: compute buffer cover on known demand only and flag it as an **upper bound**, because unrecorded demand can only reduce cover, never increase it. Same asymmetry that governs an unverified supplier list.
- **Wholly unknown usage.** A part fed only by the absent finished good. This is the full "cannot tell".

Make the synthetic data messy in realistic ways: inconsistent supplier naming across rows, some missing lead times, a few parts with a qualified supplier listed that has no lead time record.

---

## The core logic

**Step 1: explode the BOM.** Walk from finished good down to leaf parts, tracking quantity per unit of finished good and assembly depth.

**Step 2: identify single-source parts.** Parts with exactly one qualified supplier. Also flag parts where multiple suppliers exist on paper but only one has a lead time record, because that is a hidden single source.

The verdict is an **explicit lookup table, never nested conditionals**, with one test per row. Inputs are `source_type`, the supplier row count, `sourcing_list_status`, and how many of those suppliers have a lead time record.

| source_type | suppliers | list_status | with lead time | verdict |
|---|---|---|---|---|
| make | 0 | any | n/a | `made_in_house` |
| make | >=1 | any | every supplier has a lead time, and >=2 suppliers | `multi_source` |
| make | >=1 | any | otherwise | **readings disagree, exception lane** |
| buy | 0 | verified | n/a | `no_qualified_supplier` |
| buy | 0 | unverified or blank | n/a | `supplier_list_unknown` |
| buy | 1 | verified | 1 | `single_source` |
| buy | 1 | verified | 0 | `single_source_no_lead_time` |
| buy | 1 | unverified or blank | any | `supplier_list_unknown` |
| buy | >=2 | any | >=2 | `multi_source` |
| buy | >=2 | any | 1 | `hidden_single_source` |
| buy | >=2 | any | 0 | `multi_source_no_lead_times` |

Two distinctions the table preserves that conditionals would blur:

- `buy / 0 / verified` is `no_qualified_supplier`, a real and serious finding, and it is **distinct from** `supplier_list_unknown`. Someone checked and found none, versus nobody checked.
- `buy / 1 / unverified` is **not** `single_source`. An unconfirmed list of one may really be a list of two.

**A make part that also has suppliers takes no side.** Compute the verdict under both readings:

- *stale make flag*: the flag is out of date and the part is really bought, so external suppliers are the only sources.
- *genuine dual-mode*: in-house capability is real and counts as a source, so sources are one plus the external count.

If the two readings agree, report the verdict. If they differ, route to the **exception lane** showing both readings and the field that would resolve it. The exception lane is ordered by exposure under the **worse** reading, so a possible single source sorts to the top.

**Where the readings actually disagree**, enumerated rather than assumed:

- **make with zero suppliers**: no disagreement. Nothing in the data contradicts the flag, so the flag is believed. This is the trigger condition: the dual reading exists only because supplier rows on a `make` part are a contradiction, and with no supplier rows there is no contradiction.
- **make with exactly one supplier**: always disagrees, whatever the lead times. In-house is precisely the difference between one source and two, so `single_source` and `multi_source` is the whole disagreement.
- **make with two or more suppliers, all with lead time records**: agrees on `multi_source`.
- **make with two or more suppliers, any missing a lead time record**: disagrees. Under the stale-flag reading a part with two suppliers and one lead time is `hidden_single_source`; under dual-mode, in-house is a usable source that needs no lead time record because it is not a purchase, so it is `multi_source`.

An earlier draft of this brief claimed the disagreement was confined to make-with-exactly-one-supplier. That holds only if every supplier has a lead time record, which is exactly the condition this data set is built to violate.

`sourcing_list_status` **gates the verdict only. It never enters scoring.**

**Step 3: score exposure.** Not a single number. Score along separate dimensions and keep them visible rather than collapsing them:

- **Lead time to recover.** How long to qualify an alternative or wait out the disruption. Long-lead single-source is the worst case.
- **Blast radius.** How many finished units or downstream assemblies are blocked. A common part used across assemblies is worse than a deep part in one branch.
- **Buffer cover.** On-hand inventory divided by daily consumption rate, where daily consumption is annual usage from the demand plan divided by 365. Reported in days. Returns "cannot tell" when on-hand or demand is missing for that part.
- **Portability.** Supplier-owned tooling makes resourcing far slower than a catalogue part.
- **Concentration.** Multiple single-source parts sitting with the same supplier or in the same region is correlated risk, not independent risk. This one matters and is usually missed.

**Step 4: rank and explain.** Every ranked item carries the reason it ranked there. The output is not a score, it is a sentence a sourcing manager can act on: this part, one supplier, 26 week lead time, 11 days of cover, blocks 3 assemblies, supplier-owned tooling.

**Step 5: recommend, do not act.** Suggested actions per item (qualify a second source, build buffer, negotiate a safety agreement) presented as options with tradeoffs, never selected automatically.

---

## The dual reading: this system's governance primitive

Not a one-off. **Where a judgment could change the answer, compute the answer
under both judgments and let disagreement route to the exception lane.**

It has now appeared three times, each time discovered rather than designed:

1. **Make plus suppliers.** Supplier rows on a part marked `make` are a
   contradiction. Under a stale-flag reading the external suppliers are the only
   sources; under genuine dual-mode, in-house is a source needing no lead time.
2. **The supplier merge.** Supplier count is not an input, it is the output of
   name normalisation, which is a fuzzy match carrying a confidence. Two rows
   may be one supplier or two.
3. **The cross-file lead-time join.** Whether a supplier has a quotable lead
   time depends on matching its name across two files that spell it differently.

The rendering of any of these is produced on demand and never stored. **Store
structured, render prose, never store the prose**: a log holding its own
sentences cannot be re-rendered when the wording improves, and the wording is a
deliverable, being what the stage 7 review interface shows.

The pattern earns its place because the alternative is picking a default
direction, and **the safe direction is not constant**. A missed merge in the
supplier list overcounts sources and understates exposure, which is expensive. A
missed match in the lead-time join undercounts lead times and overstates
exposure, which is merely noisy. The same conservatism is protective in one
join and harmful in the other, so no global lean is correct. Computing both and
disagreeing is.

The consequence for autonomy is direct: **a stage runs at `executes` only where
the answer does not depend on the judgment.** Where it does, the stage drops to
`recommends` for that item and routes it to the exception lane carrying both
readings and the evidence that would settle it. The autonomy level is therefore
a property of the individual finding, not a blanket claim about the stage.

Stages 4 and 5 will hit this again with the correlation rules, where "same
region" and "same tier" are modelling choices rather than facts.

### Recorded at stage 3: the two disagreements are independent

Building the primitive for real surfaced something the pattern's description
hides. Readings 1 and 2 above are **not the same disagreement**, and checking
only one of them is a live defect rather than a theoretical gap.

- **Merge conflict.** The two clusterings produce different verdicts.
- **Readings conflict.** The two clusterings produce the *same* verdict, and
  that verdict is `readings_disagree`, because the part is flagged `make` while
  carrying supplier rows.

Compare the clusterings alone and the second case passes as agreement: both
readings return `readings_disagree`, they match, and a finding whose verdict
literally means *nobody can tell* is stamped `executes` and never reaches the
lane. Four parts in the generated data are exactly this. So a verdict of
`readings_disagree` is disqualifying **on its own**, independent of whether the
readings agreed.

The general form, which stages 4 and 5 inherit: *agreement between two readings
is not sufficient for autonomy if what they agree on is itself an abstention.*

### Recorded at stage 3: `readings_disagree` cannot be ranked

The exception lane orders by exposure under the worse reading, and
`readings_disagree` is deliberately **absent from the severity order**. It is not
a level of exposure, it is the absence of a settled one. The lane ranks the
concrete readings underneath it instead, which is what a person needs to work
them in the right order anyway.

### Recorded at stage 3: floors first, threshold second

Where a judgment carries a threshold, **the floors come from what the task
requires and the threshold is the dial that moves to meet them, never the
reverse.** At stage 3 the starting threshold of 0.90 failed the precision floor
of 0.95, so the threshold moved to 0.95. If no threshold had met both floors,
that would have been a finding about the normaliser rather than a reason to
lower a floor. The rejected threshold stays asserted in the tests, so the reason
for the change remains evidence rather than folklore.

## Autonomy levels, stated explicitly

This is the point of the project, not decoration.

- **Explosion, joining, and exposure identification: executes.** Deterministic, verifiable, reversible. No human in the loop needed.
- **Correlation and concentration flagging: recommends.** Judgment about what counts as correlated (same supplier, same region, same tier) is a modelling choice. Surface it, let a human confirm.
- **Recommended action: recommends, permanently.** Deciding to qualify a second source commits engineering time and money and involves supplier relationships the system cannot see. This stays a recommendation regardless of accuracy.
- **Supplier qualification itself: never.** Out of scope by design, and say so in the README.

Governance patterns come from the intake agent: typed output validation, confidence with reasons attached, append-only record of what was flagged and what a human decided, reason codes on overrides.

---

## Governance module: how reuse actually works

Do not copy the intake agent's governance code into this repo, and do not write a second one from scratch. Either:

1. Open both repos in the same Claude Code workspace, extract the governance code from the intake agent into its own package directory in that repo, give it a `pyproject.toml`, and install it here with `pip install -e ../intake-agent/packages/governance`. Or
2. If the intake agent is not available in the session, create `src/governance/__init__.py` in this repo as a thin interface only (typed result objects, confidence-with-reasons, decision log append, override reason codes) with a header comment saying it is a placeholder to be replaced by the shared package, and do not deepen it.

Say which of the two happened in the README. Two divergent governance modules with the same name is the exact failure this instruction exists to prevent.

**Resolved: option 2.** Option 1 is unavailable as written. Verified against the intake agent: `../intake-agent/packages/governance` does not exist, and agent 1 is flat-layout with no `pyproject.toml`, no `packages/` directory, and no governance module at all. Taking option 1 would mean restructuring agent 1, which is a separate repo and a separate piece of work.

One constraint this brief did not anticipate, added now: the placeholder may be thin, but its **reason-code vocabulary and decision-log record shape are copied from agent 1 verbatim**. Diverging code is annoying. Diverging data formats are expensive, because the append-only decision records are the thing anyone would eventually want to read across both agents, and a format split cannot be repaired retroactively without rewriting history.

Extraction into a genuinely shared package is **deferred until after this agent ships**. The right shared interface is not visible until two real consumers exist, and today there is one and a half.

---

## What "done" looks like

Same discipline as agent 1. Not vibes.

- A frozen eval set with hard floors, in CI on every push.
- At least one test written for something the system cannot do yet. Mark it `@pytest.mark.xfail(strict=True)` and document it in a "Known gaps" section of the README. Strict xfail means the gap is visible, CI stays green, and the test fails loudly the day someone accidentally fixes the gap without noticing. A permanently red CI is a CI nobody reads.
- Cases where the correct answer is "I cannot tell", for example a part whose supplier list is incomplete, or a part with no on-hand record. The system must say so rather than assuming single-source, multi-source, or zero inventory.
- Correctness tests on the BOM explosion itself, because a quantity error propagates silently through everything downstream. These run against a **hand-authored fixture BOM, never a generated one**. A fixture the generator produced would be the generator grading its own homework. Fifteen parts, three levels, one common part appearing at two different depths, with expected exploded quantities worked out by hand and written into a comment block above the data so a reader can check the arithmetic without trusting any code.

## What is committed and what is regenerated

The split is forced by the eval requirement rather than by taste. If the eval set regenerates from the same generator it is testing, the floors move whenever the generator changes and CI quietly stops meaning anything.

- `evals/` and `tests/fixtures/` are **committed and frozen**. Editing them is a deliberate, versioned act.
- `data/` is **gitignored and regenerated** by `python -m src.generate_data --seed 42`, which is deterministic and takes seconds, so a fresh clone still runs immediately.
- Correctness tests read committed fixtures. Property and integration tests regenerate into `tmp_path`.
- **Eval floors are never produced by the generator under test.**

This keeps the benefit of a clone that runs out of the box without the drift failure where someone hand-edits a committed CSV and the generator and the data silently disagree for a month.

**The boundary on `truth/`.** It is gitignored *while it is generator output*. When the eval set is frozen at stage 8, **its answer key freezes with it**: `evals/` ships inputs and expected outputs together, in the same commit, covered by the same manifest. A frozen eval set pointing at a regenerated answer key is exactly the drift rejected above for `data/`, relocated one directory over and harder to see. Freezing the inputs while the expectations regenerate would be worse than freezing neither, because the set would look pinned while its floors moved underneath it.

---

## Build order

1. Synthetic data generator (BOM, supplier master, lead times, demand plan, with realistic messiness)
2. BOM explosion with quantity and depth tracking, plus correctness tests
3. Single-source identification, including the hidden single-source case
4. Exposure scoring across the five dimensions, kept separate
5. Concentration and correlation detection
6. Ranked output with reasons attached
7. Review interface showing the ranking, the reasons, and the recommended options
8. Eval harness and CI gate

Build each stage to completion before starting the next. Commit at the end of each stage.

---

## Stack

Python. Governance per the section above. Streamlit for the review interface. Keep scoring logic in plain testable functions, not inside prompts, so the autonomy claims are verifiable. pytest for tests, GitHub Actions for CI.

---

## Scope discipline

Not in scope: cost optimisation, supplier scorecarding on quality or delivery performance, negotiation support, actual resourcing workflow. Those are separate agents. This one answers where the single points of failure are and how bad each one is.
