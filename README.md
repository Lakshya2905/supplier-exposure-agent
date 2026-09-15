# Supplier Exposure Agent

[![gate](https://github.com/Lakshya2905/supplier-exposure-agent/actions/workflows/gate.yml/badge.svg)](https://github.com/Lakshya2905/supplier-exposure-agent/actions/workflows/gate.yml)

Which single points of failure in a bill of materials would actually stop
production, and how badly. The agent explodes a BOM, identifies the parts with
one real source, scores the exposure along dimensions it keeps separate, and
hands a person a sentence they can act on.

Agent 3 of a multi-agent supply chain system. Synthetic data only: no real part
numbers, no real supplier names, nothing company-specific.

The interesting part of this project is not the analysis. It is the set of things
the system declines to do, and the fact that each refusal is enforced by a test
rather than by a convention.

**Every count below is a property of the synthetic dataset at seed 42, not of the
tool.** The generator is deterministic, so the figures are reproducible, but they
illustrate machinery firing rather than report findings about a supply chain. A
different seed moves all of them. The floors, the thresholds and the refusals are
properties of the system; the counts are properties of one dataset.

**Which figures are gated.** The floors in the section below are checked on every
push and block a merge. Every count in this document is an illustrative snapshot
at seed 42 and is **not gated**: asserting each one would turn a legitimate
change into a red build, which is worse than the drift it would catch.

The prose does drift, and has twice. An earlier revision carried a stale count of
84 for four commits, and a stale test total for a stage after that. So the counts
are audited against the pipeline by hand when they change, the gate reports them
under a heading saying it asserts nothing, and figures that change on every
commit are not written down here at all.

---

## The autonomy ladder

Every finding carries an autonomy level, and the level is a property of the
individual finding rather than of the stage that produced it. The same stage
executes on one part and defers on the next.

**Executes.** BOM explosion, the supplier join, exposure identification, and the
five per-part scoring dimensions where their inputs are present. Deterministic,
reproducible, and checkable against the evidence panel. At seed 42, 1021 of the
2072 dimension results execute, that being 296 scored parts across 7 measures.

**Recommends.** Anything whose answer depends on a judgment a reasonable person
could make differently. 1051 results defer, in two distinct ways: 755 because an
input is missing, and 296 because concentration carries the ceiling below.

592 of those missing inputs are the whole of `resource_days` and the whole of
`committed_at_risk`, and that is the system working rather than failing. No
dataset in this repository carries a resourcing duration or an order book, so the
tool says so for every part instead of producing figures that look complete. See
**Recovery is two measures** and **Four things a bill of materials this size
needs** below.

**Recommends permanently.** Concentration grouping, and the archetype catalogue.
Correlated exposure can be defined as same supplier, same region, or same tier,
and the three give different answers. There is an argument that once a definition
is chosen the arithmetic is deterministic and should therefore execute. The
determinism is downstream of the judgment: the question is not whether the
computation is reproducible but whether a reasonable person could have chosen
differently and got a different answer. `ConcentrationScore.autonomy` is pinned,
`autonomy_for()` is never called on it, and a test asserts the ceiling holds on
fully settled data with no uncertainty in it, since that is the input somebody
would use to argue for relaxing it.

**Where the ceiling sits is itself a decision.** For concentration each cluster
is a separate grouping claim, so the ceiling is per finding. For archetypes one
catalogue is reused across every part, so the ceiling is on the catalogue and is
confirmed once. Confirming it per part would be three hundred confirmations of a
single decision, which makes review worse rather than stronger.

**Out of scope by design.** Supplier qualification, cost optimisation, supplier
scorecarding, negotiation support, and resourcing workflow. The system recommends
actions and never selects one.

---

## The governance primitive

Where a judgment could change the answer, compute the answer under both judgments
and let the disagreement be the trigger.

It appeared five times, each time discovered by building something rather than by
design:

1. A part flagged `make` that also carries supplier rows. Stale flag, or genuine
   dual sourcing.
2. The supplier merge. Supplier count is not an input, it is the output of a
   fuzzy name match.
3. The cross-file lead-time join, where two files spell the same supplier
   differently.
4. Cover and blast radius under partial demand.
5. Supplier grouping against region grouping.

The pattern earns its place because **the safe direction is not constant**. A
missed merge in the supplier list overcounts sources and understates exposure. A
missed match in the lead-time join undercounts lead times and overstates it. The
same conservatism protects one join and damages the other, so no global lean is
correct.

### Contested and complementary disagreement

Treating every disagreement the same way is right four times out of five and
wrong the fifth. There are two kinds, and they call for opposite responses.

**Contested.** The two readings are rival answers to one question. At most one is
right. The system cannot tell, so it routes to a lane carrying both readings and
the evidence that would settle it.

**Complementary.** The two readings answer different questions. Both can be true
at once. The disagreement is structure rather than uncertainty, so it is reported
as the finding.

The test for which one is in hand:

> Could any fact settle it?

The supplier merge is settled by telephoning the supplier. Supplier grouping
against region grouping cannot be settled by any fact anybody could go and find,
because it is not a question about the world. It is a choice about what
correlated means.

So a part correlated under both definitions and a part correlated only by region
are different findings, and the output says which. At seed 42: 61 correlated
under both, 6 by region only, 140 under neither.

Getting this backwards costs in both directions. Routing a complementary
disagreement buries a real result in a queue of things that look like errors, and
the reviewer who works it has to invent an answer to an unanswerable question.
Reporting a contested disagreement asserts as structure something that is merely
unknown.

---

## Abstention is a first-class state

"I cannot tell" is a required output, not a failure mode. There are six states,
and no two of them collapse:

| state | meaning | routes for review |
|---|---|---|
| `known` | exact | no |
| `upper_bound` | computed on partial demand, true value is lower | no |
| `lower_bound` | computed on partial demand, true value is higher | no |
| `cannot_tell` | a required input is absent | yes |
| `no_recovery_path` | the supplier list was checked and is empty | no |
| `not_applicable` | the question does not attach to this part | no |

Three of them exist because collapsing them would tell a reviewer the wrong thing
to do next.

`no_recovery_path` is not missing data. Somebody checked the list and found
nobody, so recovery time is undefined by absence. Filing it as "cannot tell"
would record the most serious finding in the dataset as a gap in a spreadsheet.

`not_applicable` covers parts with no supplier at all. There is no in-house
capacity model in the data and there is not going to be one, so a review queue
that keeps presenting made-in-house parts asks a person to resolve them with data
that will never exist. 173 results land here, and every one of them would
otherwise sit in the queue.

A bound is an answer about a bound, so it executes. The bound direction inverts
between two dimensions from the identical missing row: usage sits in cover's
denominator, so unrecorded demand can only reduce cover and cover is an upper
bound; the same usage sits in blast radius's numerator, so unrecorded demand can
only add and blocked units are a lower bound. `annual_usage` therefore reports
`partial` and names no direction, and each consuming dimension names its own.

### The consequence: a work queue that is not a list of problems

Membership in a named pattern is three-valued, not boolean. A definitely false
condition excludes a part even while another condition is unknown. That single
rule is what makes the third value useful, because only parts where the unknown
is load-bearing end up undecided.

So the undecided set is exactly the parts a missing field could still move, and
the system knows which field and which outcome. At seed 42 it says:

> Fetching an on-hand count for 26 parts would settle whether they match single
> source, counted empty.
>
> Fetching a tooling owner for 9 parts would settle whether they match the
> correlated resourcing trap, the resourcing trap.

**This exists only because abstention was never defaulted to zero.** A blank
on-hand and a counted zero are different findings: one is a gap in a spreadsheet,
the other is the worst cover in the dataset. The collapse between them is not a
decision anybody makes, it is a default. Pandas reads an integer column
containing a blank as `float64`, so `0` becomes `0.0` and the blank becomes
`NaN`, and the first `int(x or 0)` downstream fuses them permanently. Every
column is therefore read as a string with `keep_default_na=False` and converted
explicitly, and `buffer_cover` branches on `is None` as its first statement,
before any expression touches the value.

The queue imputes nothing. It ranks by whether a missing field could change the
outcome, evaluated against the conditions as they stand with the field unknown,
never by a plausible value for it. A test gives two parts the same missing field
and a blast radius differing by a factor of six thousand, then asserts they come
back in part-number order, and that swapping their values does not move them.

---

## Recovery is two measures

A program manager read the tool and asked one question: for "how long it would
take to recover if that source went away", what time and activities does that
account for? The answer was purchase lead time. His reply is the specification
for this section:

> Your explanation of recovery time is exactly right, and very difficult to
> estimate as tooling and qualification can vary significantly by part (and
> doesn't always go smoothly).

Two claims, and each breaks a different assumption. Varying by part breaks the
idea that one number covers it. Not always going smoothly breaks the idea that
even a known part has ONE number, because a failed qualification adds a cycle.

So recovery is two named measures and they are never merged:

| measure | what it answers | where it comes from |
|---|---|---|
| `wait_out_days` | how long to sit the disruption out with the source you already have | `lead_times.csv`, quoted and p95 |
| `resource_days` | how long to bring an alternative source to production | `recovery_inputs.csv`, a chain of stages |

`wait_out_days` is what the tool used to call `lead_time_to_recover`. The name
was the problem: it promised both halves of the brief's dimension and delivered
the purchase lead time.

### The chain

`resource_days` sums the stages of actually replacing a source:

| stage | confidence class |
|---|---|
| finding and qualifying an alternate source | judgment |
| tooling dedicated to the part | knowable |
| engineering transfer of drawings and specs | judgment |
| first article inspection | judgment |
| qualification and reliability testing | judgment |
| ramp to rate | judgment |

**Three confidence classes, kept apart.** A purchase lead time was *reported* by
somebody with a system of record behind them. A tooling lead time is *knowable*:
nobody has supplied it, but a toolmaker could. A qualification duration is a
*judgment*, and no amount of asking turns it into a measurement. The chain keeps
each class's subtotal separately and names the weakest class it drew on. The
stages still add, because they happen one after another and elapsed days really
do add; what is refused is any statistic **across** the classes. A mean of 180
judgment days and 120 knowable days is 150 days of nothing. The reported class
never enters the chain at all, because it lives in the other measure.

**A gap makes it a bound, not a number.** An untimed stage is `cannot_tell` for
that stage and never zero, so the total under-counts by whatever it takes. The
chain is then a lower bound and the sentence names the stages nobody timed. A
chain with **no** timed stage is not a bound at all: zero is the trivial lower
bound of any duration, so it would promise a figure and deliver nothing. That
case abstains, which is the same repair the renderer already carries for a
blocked volume that could not be counted.

**The retry is modelled, never assumed.** Where a reviewer supplies how many
qualification cycles to plan for, the output carries both readings: the days if
it passes first time and the days across the cycles planned for. Where that
input is absent the tool does not quietly count one pass; it says the assumption
is unrecorded and the total is a lower bound for that reason alone. One fixture
row exists only to prove this: every stage on its path is timed, the cycle count
is the single thing missing, and the chain is still a bound.

**A cycle count, not a first-pass yield.** Either would have satisfied the ask.
A yield is a probability, and turning one into a duration needs a model of how
failures distribute. That model is a judgment, and computing it here would
attribute it to nobody. A cycle count is the same judgment made by a person who
owns it, which is where every other threshold in this system lives.

**Tooling stays categorical as well.** `tooling_owner` still feeds `portability`
unchanged. It additionally decides whether the tooling stage is on the path at
all: supplier-owned tooling does not come with you, company-owned tooling moves,
and an unrecorded owner means nobody knows which, so it bounds the total. A
stage that does not happen and a stage nobody timed both contribute zero days
and mean opposite things, so they are counted separately and named separately.

### What the split makes sayable

A part with no qualified supplier used to report "no recovery path at all". That
was true of waiting and false of recovering: an empty supplier list is precisely
the case where resourcing is the only path there is. The two measures now say so
in one sentence. The same holds for a part made in-house: you cannot place a
purchase order on your own factory, so `wait_out_days` is not applicable, but
you can qualify an outside source for the part it makes, so `resource_days`
answers. `resource_days` does not take the verdict as an input at all, which is
the clearest evidence the two were different questions.

### Why cover is not subtracted from recovery

Both are in days, so the obvious next move is `buffer_cover - resource_days` and
a statement about whether you run out before the replacement arrives. **It is
deliberately not built, and the reason is not arithmetic tidiness.**

The two quantities carry different uncertainty and subtracting them destroys
both. Cover is an upper bound wherever demand is partial, and `cannot_tell`
wherever there is no on-hand record. Recovery is a lower bound wherever a stage
is untimed, and `cannot_tell` where none is. Subtract a lower bound from an
upper bound and the error compounds in one direction: the result overstates the
margin every time, and it does so most for exactly the parts with the least data
behind them. A number carrying "at most 11 days minus at least 300 days" is not
a shortfall of 289 days; it is two bounds and an unknown wearing a minus sign.

There is a second objection that would survive even with complete data. Cover
buys time against the source you have; recovery is what you spend replacing it.
Comparing them assumes you start resourcing on the day the source fails, which
is a decision a person makes, not a fact the data contains.

So the tool reports the measures side by side, in the same sentence, in the same
unit, and leaves the comparison to the reader who knows which of those they are
doing. **If this position is wrong, the thing to change is the uncertainty
handling, not the subtraction:** a difference of two bounds could be reported
honestly as an interval, and that is a different feature from the one this
declines to build.

### What it still cannot do

The chain is timed **per part, never per candidate alternate source**. How long
qualification takes depends on which alternative you go to, and nothing in this
schema represents a candidate source. This is the known gap below, and it is
unrepresentable in the same way the first one was.

The chain is also **sequential**: it adds stages that overlap in real
programmes, so it overstates a schedule somebody has already crashed. That error
does not cancel against the under-count from untimed stages, and neither is
netted off against the other.

`recovery_inputs.csv` is **not described by `sources.csv`** in any dataset here,
so its values do not appear in the evidence panel with a system of record and an
as-of. The workings are still reachable: every stage duration, its class and
whether it was timed ride on the decision event and are named in the rendered
sentence. A deployment that supplies the file should add its manifest row too.

---

## What the system refuses to do

**No composite score.** Seven measures in four units: days, finished good units,
parts, and a categorical. There is no total, no overall, no weighted sum, and no
place to put one. Three of the seven are in days and two more are in finished
good units, and none of them is added to another: a wait-out time, a resourcing
time and a cover figure answer three different questions, as do annual demand
stopped and promised orders missed. Sharing a unit does not make two measures one
quantity.

**No normalised scale.** This is the half that matters. Twenty-six days and three
assemblies cannot be added by anybody, but "0.8 lead-time risk" and "0.6 blast
radius" add up and mean nothing. A rescaled unitless number is a composite
already assembled, whether or not anybody writes the operator. So every measure
keeps its unit, a `DimensionScore` built with a unit named `score`, `risk_index`,
`normalised` or `percent` raises at construction, and tests assert that real
values leave the 0 to 1 and 0 to 100 ranges.

**No banding.** "Long lead" and "thin cover" are thresholds, and a threshold is a
judgment. Every dimension returns its raw measure.

**No shipped threshold for long lead or thin cover.** `config/archetypes.yaml`
ships with every threshold commented out. Out of the box the system can name the
resourcing trap and cannot say "long lead" until somebody states what long means.
When a threshold is set, the number and the config version appear inside every
sentence that uses it, so the claim is attributed to the person who made it.
There is no inline slider, because a number typed into a widget and applied to
the current view is a band with no owner and no version.

**No ordinal encoding in the interface.** Colour intensity, bar length and fill
fraction are composites drawn instead of computed, which is the same objection
that rules out a radar chart, whose enclosed area is a score. `st.progress`,
progress and chart column configs, every chart type, colour gradients and
`st.slider` sit on a deny-list enforced by scanning the app source.

**No write path to source data.** The interface records decisions on an
append-only log and edits nothing. Where an abstention appears it says the
correct action is to fix the value in the system of record and re-run. Validation
flags, never fixes.

**Two orderings refused on the record.** Counting how many patterns a part
matches looks like counting and is a weighted sum with every weight set to 1.
Pareto dominance across parts would be a legitimate weightless partial order and
is deliberately not built, because across a few hundred parts carrying
abstentions the frontier is large and almost everything in it is incomparable,
and a large
frontier presented as the answer invites the mental averaging the design refuses.

---

## Autonomy as an affordance

An executed finding has nothing to click. A `recommends` finding has a control.
The model refuses to construct an executed row that carries one, so the
distinction cannot be undone by a template change or a restyle.

Executed findings are also the least inspectable part of a system whose claim is
inspectability, unless the workings are reachable. Every part row carries
read-only evidence: which supplier rows produced the verdict, which finished
goods and quantities produced the usage, which lead time record was used, and
where the two files spell a supplier differently, that the join happened. 71
parts carry that note at seed 42.

---

## Known gaps

Each is a strict xfail, so the gap stays visible, CI stays green, and the test
fails loudly the day somebody closes it without noticing. Verbatim:

**Sub-tier visibility stops one level down.** The optional
`sub_tier_sources.csv` names where a supplier sources the critical input, and
says nothing about where **that** source buys it. Two parts whose sub-tier
suppliers are different companies both buying from one tier-3 mill are
correlated in fact and independent here. The schema holds one hop, so the
reading cannot recurse.

This gap REPLACED one, and the predecessor is worth recording because it is what
the sub-tier field closed. It read: "Tier correlation is unrepresentable. The
brief names same-supplier, same-region and same-tier as three definitions of
correlated. There is no tier field anywhere in the schema, so the third reading
cannot be computed at all." The third reading now exists, its xfail is a passing
test, and the gap moved one layer down: the schema can now say who a supplier
buys from, and still cannot say who **they** buy from. That is the layer the
market research puts at roughly 42% of companies, and almost nobody passes it.

**In-house concentration is not modelled.** A part made on one internal line or
cell is a single point of failure that neither supplier grouping nor region
grouping can see, because the data has no representation of internal capacity at
all. Made-in-house parts are therefore `NOT_APPLICABLE` for concentration while
still carrying real correlated risk.

**The resourcing chain is timed per part, not per candidate alternate source.**
How long qualification takes depends on which alternative you go to: a supplier
already running the process next door and one that has to buy the capability are
not the same programme. The practitioner's point that qualification varies
significantly by part is equally a point that it varies by source. Nothing in
this schema represents a candidate source, so `resource_days` times a generic
alternative, as though every candidate were interchangeable. A part with one
near drop-in second source and a part whose only candidate needs a new process
score identically.

This gap REPLACED one, and the predecessor is worth recording because it is what
`resource_days` exists to close. It read: "lead time to recover does not include
qualification time. There is no qualification-lead-time field anywhere in the
schema, so the first half is not merely uncomputed, it is unrepresentable. A
part with a 30 day purchase lead time whose only supplier needs 40 weeks to
qualify a replacement scores identically to one that can be resourced in a
fortnight." Those two parts now score differently, a test asserts it by name,
and the durations live in `recovery_inputs.csv`. The gap moved one layer down
rather than closing: the schema can now say how long qualification takes, and
still cannot say who it would be with.

**Fractional quantities and units of measure are not supported.** Every
`qty_per_parent` is a whole number of pieces, so a BOM line of 0.5 metres of
extrusion or 2.5 kg of compound cannot be represented. This is a generator
limitation, chosen deliberately over a placeholder that would fail the build the
moment a later stage landed.

**`supplier_only` is structurally unreachable in generated data.** The generator
gives every supplier exactly one region, so a supplier cluster is always
contained in one region, and a concentrated supplier cluster therefore always
implies a concentrated region cluster. What cannot be represented is a
multinational supplier, which is precisely the commercial case that justifies
computing supplier grouping separately from region grouping: a company that fails
as a company takes all of its plants with it, wherever they are, and no region
grouping sees that coming. The one agreement class the data cannot produce is the
one carrying the argument for the second reading. It is exercised in a
hand-authored fixture, and `docs/EVAL_SCENARIO.md` specifies the second frozen
dataset that would produce it on generated data.

That document also records two other unexercised paths, and the reason none of
them is fixed by amending the generator. The merge-uncertain lane is empty at the
shipped threshold because the normaliser resolves every case in this dataset.
Engineering a supplier pair to sit just inside the uncertain band would invert
the derivation, since the threshold comes from the floors, and fitting data to
the threshold makes the number a consequence of the case built to justify it.

---

## How it is verified

Just under 500 tests, 4 strict xfails, no skips. The exact count is printed by
`python eval_harness.py` on every run and is deliberately not repeated here: it
changes on any commit that adds a test, which makes it the most drift-prone
figure in this document. An earlier revision carried a stale one for a stage.

**Hand-authored oracles.** The fixture BOMs, part master, demand plan and
supplier list are written by hand, never generated, with the arithmetic worked
out in a comment block above the data so a reader can check it without trusting
any code in this repository. A fixture the generator produced would be the
generator grading its own homework. Expectations live in separate modules that
import nothing from `src`.

**Exact arithmetic.** Quantities are `Fraction` from explosion through scoring,
so `100 x 365 / 1000` is `Fraction(73, 2)` and the fixture asserts exact equality
rather than a tolerance. Rounding happens at render and nowhere else.

**A frozen answer key with a stated boundary.** The generator records its
decisions into a truth file holding generator decisions and raw assignments, and
never anything requiring a traversal or a threshold, so that a generator bug and
an analysis bug cannot agree with each other. Cover values are therefore checked
against the hand fixtures, while abstention sets are checked against truth,
because whether a part has an on-hand record is a decision the generator made.

**The self-agreement guard.** The generator uses the verdict table to assign
intended verdicts, and the analysis uses the same table to classify observed
CSVs. So every per-row test writes its expected verdict by hand as a literal
string and none of them imports the table. Otherwise a wrong row would be wrong
in both places and the suite would agree with the bug.

**Floors before thresholds.** The name-matching floors come from what the task
requires: recall 0.99 because a missed merge understates exposure, precision 0.95
because a false merge manufactures a phantom single source. The threshold is the
dial that moves to meet them. The starting value of 0.90 failed precision at
0.917, so it moved to 0.95, where both reach 1.000. The rejected threshold stays
asserted in the tests, so the reason for the change remains evidence rather than
folklore.

**Golden rendered sentences.** The decision log stores structure and never prose.
`render(event)` produces the sentence on demand, and committed goldens make a
wording change a reviewable diff. The interface displays the renderer's output
and assembles nothing of its own.

**A frozen eval set with a stated limit.** `evals/` holds the inputs and the
answer key, committed in one commit, covered by a SHA-256 manifest. The manifest
**detects** an edit to a frozen file. It does not prevent one: a commit that
rewrites a frozen file and its manifest entry together passes the check, because
the check compares the set against its own record of itself.

The control that closes it is **branch protection on `main` requiring this gate
to pass**, and it is in effect: enforced for admins, with force pushes and branch
deletion refused. Neither layer is sufficient alone. The manifest catches an
ordinary edit to a frozen file, which protection would happily merge if the gate
were green; protection catches the rewrite of a file and its manifest together,
which the manifest cannot see.

It is a property of the remote rather than of a checkout, so a commit made and
tested purely locally is not covered until it is pushed. The harness prints the
same limit every run, because a control whose shape nobody knows is worse than
no control.

**Three layers with different standing.** Correctness against the answer key and
the behavioural invariants both gate. The regression snapshot does not, and is
never called a floor: it is produced by the system under test, so it tests only
that the system agrees with itself. A number the system produced cannot also be
the standard it is judged against.

**A corrections log.** `docs/BRIEF.md` records every defect found in this
project, because the pattern turned out to be more useful than any single entry.
The recurring failure here is not wrong code. It is a test that passes while
being subtly about the wrong thing: a clean-world control that had stopped being
clean, a headline figure of 300 of 300 verdicts matching truth that was accurate
and concealed four findings stamped as decided automatically, and a contingency
check that tested cluster keys when what was contingent was the correlation. Two
later entries record a hazard specific to this codebase: a system that refuses
concepts by name will contain those names in its refusals, so every source scan
has to distinguish a guard from a breach.

---

## Running it

```
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
python -m src.generate_data --seed 42
python eval_harness.py          # the ship gate: tests, manifest, floors
streamlit run review_app.py
```

`python eval_harness.py` is the one command, run locally before every commit and
again in CI on every push, so the two cannot diverge. It blocks on a failing
test, a **passing** xfail, a manifest mismatch, or a missed floor. It does not
block on the snapshot moving. `eval_build.py` rebuilds the frozen set and is run
by hand, never by CI.

### Three data directories, three rules

They are not interchangeable, and the whole arrangement fails quietly if they
are ever treated as though they were.

| directory | rule |
|---|---|
| `template/` | **empty files with the correct headers**, generated from `src/contract.py` so they cannot drift from the validator. Copy it. |
| `sample/` | **a labelled worked example**, small enough to read, with all three optional files filled in. It carries no answer key and nothing grades against it. |
| `evals/` | **frozen and gated.** Inputs and the answer key, committed in one commit under a manifest, never regenerated. Correctness is measured against this and nothing else. |
| `data/` | **gitignored and regenerated** from the documented seed. What a developer and CI work against. |
| `demo/` | **committed, display only.** Generated from the same seed and committed so a cold container has something to render on first page load. Never read by the harness or by any test. |

`demo/` exists because a container waking from sleep cannot regenerate data
during its first page load, so a visitor would meet a blank screen. It carries no
answer key, and `tests/test_demo_dataset.py` asserts that nothing which judges
correctness reads it. Those tests check the directory's **shape and never its
contents**, since a test that opened a demo CSV to verify it would be the first
breach of the rule it exists to protect.

The interface reads the six CSVs a real consumer would have and never the answer
key, so its verdicts come from the analysis rather than from what the generator
intended. The sixth is `sources.csv`, the extract manifest: it says which system
each file came out of and when it was pulled, which is what lets an evidence
record cite a system of record and an as-of instead of the interface inventing
one at render time. `tests/fixtures/` is committed and frozen.

A seventh input, `recovery_inputs.csv`, is **optional and absent from every
dataset here**. It carries the resourcing-chain durations, and no generator in
this repository writes one: a qualification duration is a judgment, and a
generator emitting one would be inventing the very input the tool exists to
report it does not have. Where the file is absent every part reports
`resource_days` as cannot-tell and names the stages nobody has timed. Individual
columns are optional too, one at a time, which is what keeps the frozen eval
inputs readable: they predate the file, and a reader that demanded the new
columns would make the frozen set unreadable rather than incomplete. The worked
chains live in the hand-authored fixture `tests/fixtures/tiny_recovery.csv`,
with the arithmetic in a comment block above the data.

The dashboard has no authentication and is not built to have any.

---

---

## Four things a bill of materials this size needs

All four are **optional and degrade to the behaviour that shipped without them**.
No dataset in this repository carries any of their inputs, so the shipped demo
looks exactly as it did and each feature says so rather than inventing a figure.

### Criticality: tier before assessing, and never score by it

Standard practice is to tier a BOM by criticality before assessing any of it.
Scoring three hundred lines equally is fine; scoring twelve thousand equally is
unusable. An optional `criticality` column on `part_master.csv` scopes a run.

The care is in what it is **not**:

- **Read, never derived.** The tool does not compute criticality from blast
  radius, from spend, or from anything else. A tier inferred from the measures
  is a weighted sum of them wearing a letter, and it arrives with no owner.
- **Never in a score.** `sourcing_list_status` gates the verdict only,
  `annual_spend_usd` is display-only, and this joins that list. No
  `DimensionScore` has heard of it, and `test_criticality.py` asserts the
  absence rather than trusting it.
- **Not ordered here.** Scope is a **set** of labels, never a cut-off above or
  below a level, because a cut-off asserts an ordering the tool was never told.
  The UI is checkboxes for the same reason: a slider would be that assertion
  drawn.
- **Excluding is not assessing.** A part outside the scope was not examined,
  which is different from a part examined and found fine. The run strip, the
  coverage panel and the payload all carry the count and the labels.

A part with no criticality on file is **unclassified and stays in scope**. That
is the one default here and it is the inclusive one: dropping the parts nobody
has got round to classifying would shrink the assessment to the curated slice
and report a clean result for the rest.

### One sub-tier field, which closes the tier gap

Roughly 95% of companies can see their own suppliers and fewer than half can see
one level below. An optional `sub_tier_sources.csv` names where a supplier
sources the critical input — one column, no supply-chain graph, a question a
buyer can ask on a call.

It makes the brief's third definition of correlated computable. Two parts bought
from two different companies in two different regions are not independent if both
companies buy from the same place, and neither supplier grouping nor region
grouping can see it. `concentration.BY_TIER` now does.

**`agreement` was not quietly widened.** It compares supplier with region and
says so, so a part correlated only by sub-tier source reads `neither` there —
true of those two readings, and a lie if read as "not correlated at all". So
`correlated_bases` carries every basis under which a part is correlated, and a
test asserts a tier-only part has both, so the pair cannot mislead together.

**A supplier with no entry groups with nobody.** Two suppliers who have both
declined to say are not thereby buying from the same place, and a group built
out of that absence would be a correlation manufactured from a gap and then
handed to somebody to confirm.

### Committed orders: exposure connected to consequence

Blast radius counts annual demand for the finished goods a part feeds, which
answers how much of the build stops. It does not answer what a disruption
**costs**. An optional `commitments.csv` adds `committed_at_risk`: orders already
promised that this part would stop.

They are two measures in one unit, not one measure with a multiplier. A part can
block enormous annual volume with nothing committed this quarter, and another can
block a trickle that is entirely spoken for next week; a planner does something
different about each.

**Units, not money, and that is deliberate.** `annual_spend_usd` is unscored here
because ranking by what a part costs us is the cost optimisation agent's job.
Revenue at risk is a near neighbour of that, so this counts **promised units**:
an obligation already made, in the same unit as the rest of the volumetric
reading, with no price in it. A company wanting the money can multiply outside
this system, where the price list and the argument about it both live.

The bound direction matches blast radius's, for the same reason: committed units
sit in the numerator, so a finished good absent from the order book can only
**add**. Nothing recorded at all abstains rather than reporting a lower bound of
zero, since zero is the trivial lower bound of any non-negative quantity.

### What changed: two runs, compared

A single run answers "what is exposed". The question asked on a Monday is "what
is exposed that was not last week", and answering it by reading two screens side
by side is how a new single source goes unnoticed for a month.

**The four ways a diff lies**, each of which both runs got right and the
subtraction would undo:

1. **An unknown is not a decrease.** Cover that went from 40 days to "no stock
   count on file" has not fallen to zero. `worsened` is three-valued so this case
   has somewhere to go; forcing it into a boolean would make it true or false and
   both are assertions nobody can support.
2. **A bound is not a measurement.** Two upper bounds can both fall while the
   true figures rise, so a change involving one is reported **with** its
   direction and **without** a verdict.
3. **A part that left the scope did not get better.** Otherwise the exposure
   count improves by narrowing the question.
4. **Two runs of different data are not a trend.** The comparison states which
   datasets it read and how many parts each assessed.

The surface groups changes into *worse*, *no verdict*, *better* and *scope
changed*. Those are four different instructions, not a ranking — and the *no
verdict* group is the one a diff usually drops.

---

---

## Run this on your own data

One page. No theory.

### 1. Copy the template

`template/` is nine empty files with the correct headers. Six are required and
three are optional; delete an optional file you have nothing for rather than
shipping it empty, because an empty order book and no order book are different
facts here.

| file | typically comes from | holds |
|---|---|---|
| `bom.csv` | PLM or ERP bill of materials | one row per parent-child edge |
| `part_master.csv` | ERP part master | one row per part |
| `suppliers.csv` | ERP approved vendor list | one row per qualified supplier of a part |
| `lead_times.csv` | quote history or the AVL | one row per supplier who can quote |
| `demand_plan.csv` | S&OP or the production plan | annual units per finished good |
| `sources.csv` | you, by hand | which system each file came out of and when |
| `recovery_inputs.csv` | NPI or sourcing, optional | how long approving a new supplier takes |
| `commitments.csv` | the order book, optional | units already promised |
| `sub_tier_sources.csv` | supplier declarations, optional | where a supplier buys the critical input |

`sample/` is the same nine files filled in, small enough to read, with a README
saying what every row demonstrates. Read that before filling in yours.

### 2. Three things that will bite you

**A blank is not a zero.** In `on_hand_units`, blank means nobody has counted and
`0` means somebody counted and found none. The first abstains, the second is the
worst cover in the dataset. Do not fill blanks with zeros to tidy the file.

**Units are part of the contract.** `quoted_lead_time_days` is calendar days. If
your system holds weeks, **convert the values** — renaming the header would score
every lead time at a seventh of its length and nothing would say so. The
validator catches this one by name.

**A finished good missing from `demand_plan.csv` is load-bearing.** It makes
usage *partial* rather than zero, which is what turns cover into an upper bound
and blocked units into a lower one.

### 3. Score it

Upload through **Data and coverage → Score your own extract**, or:

```bash
curl -X POST http://localhost:8000/api/score \
  -F "dataset=March extract" \
  -F "files=@bom.csv" -F "files=@part_master.csv" \
  -F "files=@suppliers.csv" -F "files=@lead_times.csv" \
  -F "files=@demand_plan.csv" -F "files=@sources.csv"
```

**It will refuse the first attempt, and the refusal is the useful part.** Every
problem names the file, the column, the row where there is one, and what the
column should contain:

```
lead_times.csv, column 'quoted_lead_time_days': this file offers
'quoted_lead_time_weeks', which is the same measure in a different unit. This
system reads 'quoted_lead_time_days', in days: the quoted purchase lead time, in
calendar days. Convert the values; renaming the header alone would score weeks
as days.
```

Nothing is coerced and no default is inferred. A column this system does not read
is reported as **ignored** rather than dropped silently, because a column you
added expecting it to be used is exactly the one you will assume was counted.

### 4. What comes out

Five surfaces. **Overview** is the shape of the set and decides nothing.
**Exposure** is one row per part with every figure in its own unit. **What to
check** is one row per *field*, ranked by how many parts one fetch would settle.
**Review** is the judgments a person has to make. **What changed** compares two
runs.

Every table exports CSV. The run summary exports PDF, with the provenance and
the digests on the first page, because a PDF outlives the screen it came from.

### 5. Optional, and worth the hour

- **`criticality` on the part master** scopes a run to the tiers you care about.
  A twelve-thousand-line BOM is not reviewable line by line, and the tool says
  out loud which parts it did not examine.
- **`recovery_inputs.csv`** turns "how long to get a new supplier approved" from
  *not enough data to say* into a figure with the untimed steps named.
- **`commitments.csv`** turns "how much of the build stops" into "and this much
  of it is already promised".
- **`sub_tier_sources.csv`** finds the correlation nothing else can see: two
  suppliers, two regions, one mill behind both.

---

## Running the scoring API

The scoring library is wrapped in FastAPI so a frontend that is not Streamlit
can reach it. **The wrap changed no answer**, and `tests/test_api.py` proves it
rather than asserting it: the frozen eval set is scored in process and through
the transport, and every one of the 1776 dimension results is compared on value,
unit, completeness, autonomy and reasons, plus the rendered sentence of every
row on every surface.

```
uvicorn src.api.main:app --reload --port 8000
```

| endpoint | does |
|---|---|
| `POST /api/score` | scores an upload, or a dataset named in the body (`demo`, `frozen`, `working`) |
| `GET /api/run/{id}` | a previous run, **re-scored from its stored inputs** |
| `GET /api/runs` | every run, newest first |
| `POST /api/decisions` | records one confirm or reject, through `interface.actions` |
| `GET /api/decisions` | the decision log, each sentence rendered on read |
| `GET /api/health` | liveness, and which datasets the container can see |

### Three things the transport is careful about

**A run is re-scored, never replayed.** The run store holds the input CSVs and a
digest of each, and nothing else. Fetching a run scores those bytes again, so a
wording change reaches a run recorded last month and a scoring change shows up
as a changed answer instead of the record quietly disagreeing with the code that
claims to have produced it. The cost is accepted: about a second, and a run is
not reproducible if its inputs are deleted from under it, which the endpoint
says out loud rather than substituting another dataset.

**Nothing is rounded on the way out.** Cover is `Fraction(73, 2)` exactly, and it
crosses as `{"type": "exact", "numerator": 73, "denominator": 2}`. A float there
would move rounding out of the renderer, where this project puts it, into
transport, where nobody would look for it. `null` and `0` stay distinct because
they are different findings. `UNBOUNDED` crosses as `{"type": "unbounded"}`,
because cover with nothing consuming it is an answer and not an absence. And
every non-plain value is tagged, because a `(quoted, p95)` pair and a rational
are both two integers, and a caller holding only the payload cannot tell them
apart by branch order the way the renderer does.

**No judgment lives in the HTTP layer.** A decision is recorded through
`interface.actions.apply` and never around it, so every refusal that module
makes still holds over the wire: an anonymous decision is refused, a rejection
without a reason is refused, and the same person clicking the same button twice
is refused as one judgment arriving twice. The control is **found** on the
Review surface, never constructed from the request, because a control's
existence is the autonomy claim and building one here would hand a reviewer
power this system does not offer them.

### The interface

`web/` is a Next.js application using IBM Carbon v11 at the Gray 10 theme. It
replaces the Streamlit surface rather than wrapping it: the four surfaces are
the same four, renamed for clarity, and every figure on them is computed in
Python and served by the API.

```
cd web && npm install && npm run dev      # needs the API on :8000
```

| surface | job | the row is |
|---|---|---|
| Overview | the shape of the whole set. Decides nothing | — |
| Exposure | what is worst | a part |
| What to check | what one fetch settles the most | a **field**, never a part |
| Review | judgments waiting for a person | a cluster |
| Decision log | who decided what, when and why | an event |

**Why Carbon.** Every competitor leads with a branded composite index. This
tool's thesis is refusing to combine, so the interface has to make that refusal
read as a position rather than an unfinished feature. Carbon is built for dense
enterprise data, is accessibility-tested, and its restraint does the work that
decoration cannot.

**Where an index would go, there are words.** `src/binding.py` names what binds
on a part and what blocks it, and it does so by comparing **states, never
magnitudes**. "Which dimension is worst" would be 300 days measured against
12,000 finished-good units, and no unit makes those the same quantity; a
function answering it would be the composite this project refuses, hidden inside
a superlative. So a dimension binds when it reaches the worst value it can
express **without a threshold**: nobody to wait on, stock counted and empty,
tooling that does not come with you. How much of the build stops and how long
resourcing takes have no entry, because neither has a worst value until somebody
states a threshold, and a part whose only notable feature is a large blast
radius therefore binds on nothing. The screen says so rather than promoting the
largest number on the row.

**Three kinds of unknown, three treatments.** Something that could be
established and has not been is a warm-grey tag; a question that does not attach
to this part is a cool-grey one; a threshold nobody has configured is an info
notification pointing at the file and the key. They are not interchangeable: one
is settled by a phone call, one by nobody ever, and one by editing
`config/archetypes.yaml`. Nothing renders as zero, blank, or a dash.

**One restyle, written down.** Carbon ships `Tag` at a 16px radius, which is a
pill, and the rule here is square corners everywhere. `globals.scss` sets that
radius to 0 and touches nothing else about the component, so the accessible
markup, contrast and focus behaviour Carbon tested are all intact.

**One chart is not Carbon, and the reason is geometry.** The region map is drawn
with the same library the tested Streamlit implementation uses, because its
shapes carry a decision this repository has already made and asserted: India is
drawn **including its full claimed territory**, from a boundary vendored under
CC BY 4.0, since the built-in `IND` polygon follows a different convention and
stops around 35.5N. Carbon Charts would need world geometry supplied from
somewhere else, and re-sourcing it is exactly how a decision like that gets lost
without anything failing — the map would simply draw a smaller India.
`tests/test_map_geometry.py` asserts the northern and eastern reach of the one
copy, which the API serves at `/api/assets/india-claimed.geojson` so there is no
second copy for that test to miss. The map's colours are Carbon tokens read from
the live document, and the scale starts **above** the land colour so that the
least-exposed region and "not a region at all" cannot render alike.

### The words on the screen

**The test applied to every string: a procurement analyst with no statistics
background reads it once and knows what to do next.** The vocabulary was a
modeller's, and each term was exact and told that reader nothing.

| was | is |
|---|---|
| abstains instead of imputing | we do not have this data, so this part is not scored on it |
| p95 lead time | worst case lead time |
| lead time to recover | how long until parts flow again from this supplier |
| blast radius | how much of the build stops |
| buffer cover | how long current stock lasts |
| portability | how hard it is to move to another supplier |
| correlated exposure | shares a supplier or region with other exposed parts |
| cannot tell / not established | not enough data to say |
| hidden_single_source | several suppliers listed, only one can actually quote |
| nobody to call | no supplier on file |
| what should I go and find out | what to check next |
| the resourcing trap | one supplier, supplier-owned tooling |

**It is one rewrite, in `src/governance/render.py` and `src/scoring.py`.** Prose
is produced by `render()` on demand and never stored, so both interfaces changed
together and the golden files made every reworded sentence a reviewable diff
rather than a surprise.

**What deliberately did not get simplified.** Bound direction. An upper bound
still reads "at most" and a lower bound "at least", now with the consequence
spelled out: *at most 11 days, and possibly less*. They are never softened into
a shared hedge like "roughly", because the whole system turns on those two
pointing opposite ways from the identical missing row: unrecorded demand can
only **reduce** cover and can only **add** to what is blocked. A reader who
cannot tell which way a figure is wrong has a number they cannot use, which is
worse than plain-sounding prose that means nothing. `test_scoring.py` asserts
both directions by name.

**One thing in the brief was not implemented as written.** It mapped "upper
bound" to "at least this long, possibly longer". That is the wording for a
*lower* bound; an upper bound means the true figure is at most the one shown.
Implementing it verbatim would have inverted the direction on cover, which is
the defect the corrections log exists to catch. Both directions are implemented
correctly and the discrepancy is recorded here rather than silently resolved.

**Internal keys are never rewritten, only presented.** `south_asia` is the
identity a cluster is decided against and every row of the decision log joins on
that exact string. `render.display_subject` title-cases a subject **only when it
contains an underscore**, which separates a region key from a supplier name:
supplier names carry spaces and their own capitals, and the dataset deliberately
contains `calder corporation` lowercase, because a name as spelled is evidence
and tidying it would hide the messiness the matcher exists to survive.

### Deploying it

**The backend** needs a host that stays awake. `Dockerfile` and `Procfile` are
both here; the container is the fuller statement. Mount a volume at `/data`:
`SEA_RUNS_DIR` and `SEA_DECISIONS_DIR` are written at request time, and a
decision log that resets on deploy is the defect `governance/store.py` exists to
close, one layer out.

**The frontend** is static and goes on Vercel with `web/` as the root directory.
The two deploy separately on purpose: the frontend is the thing a link points at
and Vercel does not sleep it, and the backend is the thing that must not sleep,
which is a different requirement served by a different host.

Three things catch people out, in the order they catch them:

1. **Deployment Protection is on by default.** A fresh Vercel project puts every
   deployment behind a Vercel login, so the link you send opens a sign-in page
   for an account the recipient does not have. That is the same dead link this
   whole move was meant to fix, wearing a different hat. Turn it off under
   *Project → Settings → Deployment Protection → Vercel Authentication*, or add
   a protection bypass, before you send the URL to anybody.

2. **`NEXT_PUBLIC_API_BASE` is inlined at build time, not read at runtime.**
   Adding it to the project settings does nothing to a deployment that is
   already built. Set it, then **redeploy**. Without it the page tries to reach
   `127.0.0.1:8000`, which is the *visitor's* machine; the error state says so
   in those words rather than telling a stranger to run uvicorn.

3. **The backend needs a host that stays awake and a volume.** Mount `/data`:
   `SEA_RUNS_DIR` and `SEA_DECISIONS_DIR` are written at request time, and a
   decision log that resets on deploy is the defect `governance/store.py` exists
   to close, one layer out.

Neither half has authentication and neither is built to have any. Deployment
Protection is Vercel's, not this application's, and it protects the frontend
only: an unprotected backend URL is an unprotected backend.

## Where the reasoning lives

| document | contents |
|---|---|
| `docs/HANDOFF.md` | **start here.** Every feature, why it works that way, and what will bite you |
| `docs/BRIEF.md` | the spec of record, the governance primitive, and the corrections log |
| `docs/EVAL_SCENARIO.md` | what the second frozen dataset has to exercise, and what it must not do |
| `docs/DATA_DICTIONARY.md` | columns, types, units, and null semantics |
| `CLAUDE.md` | the working rules this project is built under |
