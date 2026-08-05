# Supplier Exposure Agent

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
change into a red build, which is worse than the drift it would catch. The prose
does drift, and has: an earlier revision carried a stale count of 84 for four
commits. So the counts are audited against the pipeline by hand when they change,
and the gate reports them under a heading that says it asserts nothing.

---

## The autonomy ladder

Every finding carries an autonomy level, and the level is a property of the
individual finding rather than of the stage that produced it. The same stage
executes on one part and defers on the next.

**Executes.** BOM explosion, the supplier join, exposure identification, and the
four per-part scoring dimensions where their inputs are present. Deterministic,
reproducible, and checkable against the evidence panel. At seed 42, 1021 of the
1480 dimension results execute, that being 296 scored parts across 5 dimensions.

**Recommends.** Anything whose answer depends on a judgment a reasonable person
could make differently. 459 results defer, in two distinct ways: 163 because an
input is missing, and 296 because concentration carries the ceiling below.

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

## What the system refuses to do

**No composite score.** Five dimensions in four units: days, finished good units,
parts, and a categorical. There is no total, no overall, no weighted sum, and no
place to put one.

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

**Tier correlation is unrepresentable.** The brief names same-supplier,
same-region and same-tier as three definitions of correlated. There is no tier
field anywhere in the schema, so the third reading cannot be computed at all.
Choosing two of three is a scoping decision and should not look like the data
happened to support exactly the right two.

**In-house concentration is not modelled.** A part made on one internal line or
cell is a single point of failure that neither supplier grouping nor region
grouping can see, because the data has no representation of internal capacity at
all. Made-in-house parts are therefore `NOT_APPLICABLE` for concentration while
still carrying real correlated risk.

**Lead time to recover does not include qualification time.** The brief defines
it as how long to qualify an alternative or wait out the disruption. The data
carries quoted and p95 purchase lead times, so this dimension answers the second
half only. There is no qualification-lead-time field anywhere in the schema, so
the first half is not merely uncomputed, it is unrepresentable. A part with a 30
day purchase lead time whose only supplier needs 40 weeks to qualify a
replacement scores identically to one that can be resourced in a fortnight.

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

462 tests, 4 strict xfails, no skips.

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
the check compares the set against its own record of itself. The control that
closes that is branch protection requiring the gate to be green before a merge,
which applies on a remote and **is not in place for this repository as it stands
locally**. The harness prints the same limit every run, because a control whose
shape nobody knows is worse than no control.

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

`data/` is gitignored and regenerated from the seed above in under a second.
`tests/fixtures/` is committed and frozen. The interface reads the five CSVs a
real consumer would have and never the answer key, so its verdicts come from the
analysis rather than from what the generator intended.

The dashboard has no authentication and is not built to have any.

## Where the reasoning lives

| document | contents |
|---|---|
| `docs/BRIEF.md` | the spec of record, the governance primitive, and the corrections log |
| `docs/EVAL_SCENARIO.md` | what the second frozen dataset has to exercise, and what it must not do |
| `docs/DATA_DICTIONARY.md` | columns, types, units, and null semantics |
| `CLAUDE.md` | the working rules this project is built under |
