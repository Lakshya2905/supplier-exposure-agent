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

### Recorded at stage 5: contested disagreement and complementary disagreement

The primitive as first written treats every disagreement the same way: compute
both, and route when they differ. That is right for the first four appearances
and wrong for the fifth, and the difference is not a detail. **There are two
kinds of disagreement, and they call for opposite responses.**

**Contested.** The two readings are rival answers to ONE question. At most one
is right. Disagreement means the system cannot tell, so it routes and carries
both readings plus the evidence that would settle it. The supplier merge is
contested: either those two rows are one supplier or they are two.

**Complementary.** The two readings answer DIFFERENT questions. Both can be
true at once. Disagreement is not uncertainty, it is structure, and it is the
most useful thing the analysis produces, so it is REPORTED rather than routed.
Supplier concentration and region concentration are complementary: a part can
genuinely be correlated by geography and not by company, and saying so is a
true statement about the world.

**The test for which one you are holding: could any fact settle it?**

    settleable disagreement    -> uncertainty -> route it
    unsettleable disagreement  -> structure   -> report it

The stage 3 merge is settled by telephoning the supplier. Supplier-versus-region
cannot be settled by any fact anybody could go and find, because it is not a
question about the world at all; it is a choice about what "correlated" means.
A disagreement with no possible resolving fact is not a gap in the data.

Getting this backwards in either direction is costly. Routing a complementary
disagreement buries a real finding in a queue of things that look like errors,
and a reviewer who resolves it has to invent an answer to an unanswerable
question. Reporting a contested disagreement asserts as structure something
that is merely unknown.

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

**The abstention rule, stated generally.** Autonomy requires agreement on a
*settled answer*. Agreement is necessary and not sufficient. Two readings
agreeing on an abstention is unanimous uncertainty, not a decision, and
unanimous uncertainty is exactly as undecided as disagreement is.

The test is therefore two-part and both parts must hold before anything
executes:

1. the readings agree, and
2. what they agree on is an answer rather than an abstention

Stages 4 through 8 inherit this unchanged. It applies per dimension per part at
stage 4, not per stage: a dimension that abstains on a part cannot be rescued by
the fact that both of its readings abstained identically.

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

### Recorded at stage 4: a bound is an answer, and its direction belongs to the consumer

Partial demand does not abstain, it bounds. And the bound direction is not a
property of the missing data, it is a property of where the number lands: usage
in a denominator makes cover an UPPER bound, the same usage in a numerator makes
blast radius a LOWER bound. So the join reports `partial` and names no
direction, and each consuming dimension names its own.

This is the third appearance of the same shape. The safe direction was not
constant between the supplier merge and the lead-time join, and it is not
constant between cover and blast radius either. Any future function that reports
incompleteness to more than one consumer should report the FACT of it and let
each consumer interpret it.

### Recorded at stage 4: absence is not zero, in both directions

A finished good absent from the demand plan is not a finished good with zero
demand, and the two must stay distinguishable through scoring exactly as a blank
on-hand and a counted zero must. The consequence is sharper than it looks: a
part with a recorded zero on-hand and an absent finished good abstains, because
an empty buffer is zero days of cover under any positive consumption but
unbounded cover under none, and the data cannot say which.

### Recorded at stage 4: the composite is enabled by normalisation, not by addition

Refusing to sum the dimensions is the easy half and it is not the half that
matters. Heterogeneous units cannot be added by anyone; rescaled unitless
numbers can be added by everyone. So the rule is that **every measure keeps its
unit**, and a dimension expressed as a 0-to-1 or 0-to-100 figure is a composite
already assembled, whether or not anybody writes the operator.

---

## Corrections log: this project's actual failure mode

Kept because the pattern is more useful than any single entry. **The recurring
defect here is not wrong code. It is a test that passes while being subtly about
the wrong thing.** Each instance below was green, and each was green for a
reason that had drifted away from what the test was supposed to establish. Code
that is wrong announces itself. A test that is about the wrong thing announces
that everything is fine.

Three instances of the original shape, then two of a second, then three more that
sharpen it. Entries 1, 2, 3 and 6 are a proxy standing in for the property.
Entries 4 and 5 are a check that malfunctioned on correct code. Entry 7 is the
property held everywhere except at the exit. Entry 8 is not about a test at all:
it is the same failure performed by a reviewer rather than by an assertion, which
is why it belongs here rather than in a postmortem.

**1. The clean-world control stopped being clean.** `zeroed()` enumerated the
damage knobs inline. Two knobs added later were not added to the list, so
setting "all messiness to zero" left two forms of damage running, and the test
that proves an undamaged world has no findings passed under its own name while
testing a world that was still damaged. The test was about *the knobs somebody
remembered*, not about *all knobs*. Fixed by classifying every `n_*` field
generically and asserting that the classification is exhaustive, so a new knob
cannot be silently omitted.

**2. Verdicts matched truth while autonomy was wrong.** Stage 3 reported 300 of
300 verdicts matching the answer key, and that was true. It was also hiding four
findings whose verdict literally read `readings_disagree` and which were
nonetheless stamped `executes` and never reached the exception lane. The test
compared the verdict string. Nothing compared the autonomy, so a headline number
that was completely accurate concealed a governance defect underneath it. Fixed
by asserting that no finding meaning "nobody can tell" is ever decided
automatically.

**3. Contingency was detected on the wrong noun.** Stage 5 needed to find
concentrations that exist only if an unresolved supplier merge is confirmed. The
first implementation tested whether the cluster KEY was new under the merged
reading. It passed. It passed for the wrong reason: two singleton suppliers whose
names might be one supplier exist as keys under BOTH readings, so key novelty is
never true for exactly the case the generator's mirror trap was built to produce.
What is new under merging is the CORRELATION, not the cluster. Fixed by reading
membership per part under both readings and comparing that.

**4. A regex flagged its own guard.** The visual pass checked that no
`box-shadow` other than `none` had crept in, using `box-shadow:\s*(?!none)`.
Every shadow in the file is `none` and the check reported a violation anyway.
`\s*` matches the empty string, so the engine backtracked to zero width and
evaluated the negative lookahead at the position of the space rather than at the
word, where "none" does not literally begin. The pattern was asking a question
one character away from the one intended.

**5. A scan flagged a promise not to do the thing.** The same pass searched for
`dark` to confirm no dark variant had been introduced. The only match was the
first line of the theme file: "Light only. No dark variant and no toggle." The
scan found the commitment and reported it as the breach.

**6. Three guards enforced one guarantee and all three checked the notation.**
The chip palette guaranteed that "no chip is darker, stronger or warmer than
another, so no reading of the set produces an order." Three mechanisms enforced
it: a comment in `.streamlit/config.toml`, the `.badge` rule declaring one
background and one colour, and
`test_the_category_palette_is_nominal_by_arithmetic` asserting equal HSL
saturation and lightness. All three passed. The guarantee was false. HSL
lightness is not perceptual lightness, and in CIELAB the six completeness
entries spanned 15.3 L\* points and sorted into a clean brightness ramp in
declaration order, so the enum's own order was leaking into the perceptual
channel. Two of the three guards were also bypassed at runtime by inline styles
that `chip_colour()` wrote per category, including a per-category text tint.
Fixed by deleting the hue map: the label already carried the category, and
`CLAUDE.md` already required that stripping colour lose no information.

**7. The rule held for eight stages and collapsed at the sentence.** Missing and
zero are different facts, and this codebase enforces that harder than anything
else it does: `read_part_master` refuses to coerce a blank to zero, `buffer_cover`
separates the two before any arithmetic and says so in capitals, and
`TestMissingOnHandVersusRecordedZero` asserts they differ at every level. Then
`blast_radius` rendered "blocks at least 0 finished good units" ten times on the
landing surface. The dimension carries two facets, a structural reach that is
KNOWN and a blocked volume that inherits the demand plan's gaps, and its own
reason text says exactly that. The renderer rendered only the volumetric facet,
so a part that certainly stops a finished good read as blocking nothing, and the
absence arrived as the number zero wearing a bound prefix that promised a figure.

Forty characters earlier in the same sentence sat the correct treatment of the
same problem: "no on-hand record, so cover is unknown". One absence in words, one
as a zero, in one sentence.

> A guarantee enforced through a pipeline is not enforced at its exits. Every
> layer that turns structure into something a person reads is a place the
> guarantee has to be restated, because a renderer that drops a facet is
> indistinguishable, to a reader, from a model that never had it.

The near-miss is worth recording with it. The obvious fix keys on `value == 0`,
and that is wrong for the same reason the bug is wrong: partial usage whose
recorded goods happen to total zero is a RECORDED zero, so inferring the branch
from the value reintroduces the collapse inside its own repair. It does not occur
on seed 42, which makes it latent rather than absent, and latent is the worse of
the two for something a renderer keys on. The fix keys on the branch that set the
completeness, named rather than reduced to a boolean so that a third usage state
must declare itself instead of inheriting a reading.

**8. Trust inherited from a subagent, reported as verification.** A review agent
reported that all four gap xfails asserted the existence of a name rather than a
behaviour. Two were checked directly against the code. The other two were not,
and all four were reported upward as verified. One of them,
`test_fractional_quantities_are_supported`, was already behavioural: it runs the
generator and asserts a non-integer quantity appears in real BOM rows. The claim
that shipped was "all four", the evidence supported "two, and a pattern".

This happened in the same session, and in the same commit, as the fix for
accepting a proxy in place of the property. It is the second instance of the same
shape here. Earlier in the same session a measured claim about the chip palette
was passed upward with a severity ("two chips fail WCAG AA today") that direct
verification later reduced to a latent defect in unreachable code, and a learning
was written with `source: cross-model` when the second voice was another instance
of the same model.

> A subagent's finding is evidence, not verification. Delegating the search does
> not delegate the checking, and the plausibility of a claim rises with the effort
> that produced it, which is exactly what makes an expensive report the easiest
> one to forward unchecked.

The counter-practice is mechanical, because judgment is what fails here: state
the count, then check each member and mark it. "Three of four, verified
individually" and "all four, per the agent" are different claims, and only the
first is a finding. Where a claim is forwarded unchecked, forward it labelled.

Entry 6 is instances 1 to 3 again, with one addition worth stating on its own.

> **Redundant guards that share an assumption read as confirmation while
> providing none.** Independence is not about how many guards exist, or how far
> apart they live in the tree. It is about whether they can fail SEPARATELY.
> Guards that inherit the same premise fail together and silently, and their
> agreement is what stops anybody looking.

Three checks agreeing looked like triangulation. It was one check performed three
times. This is the sharper form of the defect this log is about: testing the
wrong thing leaves you with no evidence, and redundantly testing the wrong thing
leaves you with false evidence, because the count of passing guards becomes the
argument against investigating. When adding a guard, the question is not "is this
covered elsewhere" but "what premise does this share with the guards already
there." If the answer is the same one, it adds confidence without adding
coverage.

A corollary for review: a guarantee defended by several mechanisms deserves MORE
suspicion of its premise, not less. Ask what all of them assume, and verify that
assumption directly and numerically at least once.

Severity, stated accurately, because it matters to how this entry is read: nine
of the eleven hues never reached a badge, so no reader ever saw the ramp. It was
a latent trap rather than a live defect. That is the more dangerous timing, not
the less: a wrong guard is most trusted before the code it guards is written,
which is exactly when somebody first relies on it.

The common thread across the first three, and six: a proxy stood in for the
property that mattered, was correlated with it most of the time, and diverged
precisely at the interesting case. The counter-practice is to state what a test
is establishing in one sentence and then check that the assertion establishes
THAT, rather than something that usually travels with it. Hand-written
expectations and the self-agreement guard exist for the same reason and are not
sufficient alone: instance 3 had hand-written expectations and still passed.

**Instances 4 and 5 are a hazard specific to this codebase, and it will keep
recurring, so it is stated as a rule rather than continued as a list.**

> A system that refuses concepts by name will contain those names in its
> refusals. Every source scan must therefore distinguish a guard from a breach.

This codebase refuses composites, bands, normalised scales, severity colours,
imputation and dark mode, and it refuses them in writing: in constants like
`FORBIDDEN_UNIT_WORDS`, in docstrings that explain at length why a weighted sum
is not permitted, and in comments promising there is no night mode. Every one of
those is a string containing the forbidden token. A naive scan finds the
strongest statements of the rule and reports them as violations of it.

The consequences are worse than a red build. A test that fails on correct code
teaches the next person to delete the test, which removes the guard and leaves
the refusal undefended. It has already forced two mitigations, and both are the
same idea: `tests/codescan.py` strips docstrings and comments before scanning,
and its `functions_only` mode additionally drops module-level statements so that
a module DECLARING the forbidden vocabulary as data is not mistaken for using
it. Anything new in this class needs the same treatment before it is trusted.

---

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
