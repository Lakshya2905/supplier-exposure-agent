# Handoff

Everything this system does, why it does it that way, and what will bite you.

**Read this first, then `docs/BRIEF.md` for the spec, `DESIGN.md` for the
interface contract, and `CLAUDE.md` for the working rules.** Where this document
and those disagree, they win and this is stale.

**Every count below is a property of the synthetic dataset at seed 42, not of the
tool.** The generator is deterministic, so the figures reproduce, but a different
seed moves all of them. The floors, the refusals and the structure are properties
of the system; the counts are properties of one dataset.

---

## 1. What it is

An internal review tool that answers one question: **which single points of
failure in a bill of materials would actually stop production, and how badly.**

It explodes a BOM, identifies parts with one real source, scores exposure along
measures it keeps separate, and hands a person a sentence they can act on.

Agent 3 of a multi-agent supply chain system. **Synthetic data only** — no real
part numbers, no real supplier names, nothing company-specific.

The interesting part is not the analysis. It is the set of things the system
declines to do, and the fact that each refusal is enforced by a test rather than
by a convention. If you read one thing after this section, read §4.6.

---

## 2. Shape of the thing

Three deployable pieces and one library.

| piece | what | where |
|---|---|---|
| `src/` | the scoring library. Every judgment lives here | imported |
| `src/api/` | FastAPI over that library. **No judgment lives here** | a container |
| `web/` | Next.js + IBM Carbon v11. Paints; decides nothing | Vercel |
| `review_app.py` | the original Streamlit surface, still working | local |

The Streamlit app has not been deleted. It reads the same library directly and
is the thing `tests/rendered.py` measures; it is not the deliverable any more.

**The split is load-bearing.** Every figure the frontend draws is computed in
Python and asserted there. When you are tempted to compute something in
TypeScript, that is the moment to stop: a judgment in `web/` is a judgment no
Python test can reach.

### 2.1 Where the code is

Roughly in the order data moves through it.

| module | holds |
|---|---|
| `src/synthetic/` | the generator, the verdict table, the answer key |
| `src/readers.py` | the one place null encoding is decoded. **Missing-vs-zero is won or lost here** |
| `src/contract.py` | what each file must contain, checked before anything reads it |
| `src/explosion.py` · `src/demand.py` | the BOM walk and the usage join |
| `src/identify.py` · `src/normalise.py` | the sourcing verdict and the supplier name match |
| `src/scoring.py` | the seven measures. No composite, and no place to put one |
| `src/recovery.py` | the resourcing chain and its confidence classes |
| `src/commitments.py` · `src/subtier.py` · `src/criticality.py` | the three optional inputs |
| `src/concentration.py` | clustering under three readings |
| `src/binding.py` | what binds and what blocks, by state |
| `src/archetypes.py` · `src/ranking.py` | named patterns, and the orders that exist |
| `src/changes.py` | two runs compared |
| `src/governance/` | the decision log and the renderer. **All prose lives here** |
| `src/interface/` | surfaces, evidence, dashboard aggregates |
| `src/pipeline.py` | CSVs on disk to the three review surfaces |
| `src/api/` | HTTP. Encoding in `encode.py`, run store in `runs.py` |
| `web/lib/` | the wire decoder, labels, CSV, the exposed-parts walk |
| `web/components/` · `web/app/` | the Carbon shell and the six surfaces |

---

## 3. Running it

```bash
python -m venv .venv && source .venv/bin/activate   # NOT venv/ — see §13.2
pip install -e ".[dev]"
python -m src.generate_data --seed 42
```

Three processes, and you want all three:

```bash
uvicorn src.api.main:app --reload --port 8000   # the API
cd web && npm install && npm run dev            # the interface, on :3000
streamlit run review_app.py                     # the original surface
```

The gate is the definition of done:

```bash
python eval_harness.py       # SHIP GATE: PASS, or the task is not finished
```

It blocks on a failing test, a **passing** xfail, a manifest mismatch, or a
missed floor. For the browser checks you also need a browser once:

```bash
python -m playwright install chromium
```

---

## 4. The analysis

### 4.1 The autonomy ladder — this is the product, not a detail

Autonomy is a property of the **individual finding**, not of the stage that
produced it. The same stage executes on one part and defers on the next.

| level | what |
|---|---|
| **Executes** | explosion, the supplier join, exposure identification, the six per-part measures where inputs exist |
| **Recommends** | correlation and concentration flagging — a human confirms |
| **Recommends permanently** | concentration grouping and the archetype catalogue |
| **Never** | supplier qualification. Out of scope by design |

**Autonomy is an affordance, never an appearance.** An executed finding has
nothing to click. `Row.__post_init__` refuses to construct an executed row
carrying a control, so the claim survives a restyle — and `POST /api/decisions`
*finds* its control on the Review surface rather than constructing one, so it
survives the network too.

### 4.2 The sourcing verdict

An **explicit lookup table**, never nested conditionals, with one test per row.
The per-row tests hard-code their expected verdict by hand and **must not import
the table** — otherwise a wrong row would be wrong in both places and the tests
would agree with the bug.

`single_source`, `hidden_single_source`, `multi_source`,
`multi_source_no_lead_times`, `single_source_no_lead_time`,
`no_qualified_supplier`, `supplier_list_unknown`, `made_in_house`,
`readings_disagree`.

`sourcing_list_status` gates the verdict **only**. It never enters scoring.

### 4.3 The seven measures

| Measure | Unit | From |
|---|---|---|
| `wait_out_days` | days — a `(quoted, worst case)` pair | `lead_times.csv` |
| `resource_days` | days — a chain total, untimed steps named | `recovery_inputs.csv` *(optional)* |
| `blast_radius` | finished-good units a year | the demand plan |
| `committed_at_risk` | finished-good units | `commitments.csv` *(optional)* |
| `buffer_cover` | days | on-hand ÷ daily use |
| `portability` | categorical | `tooling_owner` |
| `concentration` | parts | clustering |

**Seven, and two of those splits are the point.** The brief's first dimension
was two questions sharing one name: waiting a disruption out and resourcing
around it have different inputs, different confidence and different completeness.
Blast radius and committed orders are the same shape — annual demand stopped is
not orders already promised, and a planner acts differently on each.

**Three are in days, two in finished-good units, and none is added to another.**
Sharing a unit does not make two measures one quantity.

No total, no weight, no `__add__`, no normalised variant of any value. Every
measure keeps a physical unit, because a unitless number in a fixed range is a
composite already assembled. A chart may draw one measure in its own units;
**nothing puts two on one axis**, which is why there is no radar plot.

### 4.4 Where an index would go, there are words

`src/binding.py` names what **binds** on a part and what **blocks** it, and the
care is in what it refuses. "Which measure is worst" would be 300 days against
12,000 finished units, and no unit makes those the same quantity — a function
answering it would be the composite, hidden inside a superlative.

So it compares **states, never magnitudes**. A measure binds when it reaches the
worst value it can express *without a threshold*: nobody to wait on, stock
counted and empty, tooling that does not come with you. Blast radius, resourcing
days and committed orders have **no entry** — none has a worst value until
somebody sets a threshold — so a part whose only notable feature is the biggest
number on the row binds on nothing, and the screen says so.

Two lists, not one: *binds* (as bad as it gets) and *blocks* (nobody can tell)
are different instructions.

### 4.5 Two kinds of disagreement

The test is one question: **could any fact settle it?**

- **Settleable** → uncertainty → routes to a lane with both readings and the
  evidence that would settle it.
- **Unsettleable** → structure → reported as the finding.

Supplier-grouping versus region-grouping cannot be settled by any fact anybody
could go and find. Routing it to a lane would bury a real result among things
that look like errors.

Sub-tier grouping is a **third** reading. `agreement` still compares supplier
with region and says so, so a part correlated only by sub-tier source reads
`neither` there — true of those two, a lie about the part. `correlated_bases`
carries every basis, and a test asserts a tier-only part has both so the pair
cannot mislead together.

### 4.6 Abstention is a first-class output

Six states, and no two collapse: `known`, `upper_bound`, `lower_bound`,
`cannot_tell`, `no_recovery_path`, `not_applicable`. Only `cannot_tell` routes
for review.

**Missing and zero are different facts.** A blank on-hand means *no record* and
never reads as zero; a recorded zero is real. Absence is never dimmed, never
blank, never a dash — it renders at the same weight and footprint as an asserted
value.

**A bound is not an abstention**, and the direction inverts between two measures
from the identical missing row: usage sits in cover's denominator, so unrecorded
demand can only *reduce* cover; the same usage sits in blast radius's numerator,
so it can only *add*. `annual_usage` therefore reports `partial` and names no
direction, and each consuming measure names its own.

**Zero is not a bound.** "At least 0 units" is a true statement carrying no
information, dressed as a measurement. Where nothing is timed, nothing is
recorded, or no demand is known, the measure abstains instead. This has been got
wrong twice and repaired twice — once in the renderer, once in the exposure
table — so assume it is the next thing to get wrong.

---

## 5. Evidence — every claim shows its work

Each citation carries six fields:

1. **source id** — file and row, attached by the reader *before* its sort
   reorders anything
2. **system of record** — from `sources.csv`, plus `recorded` vs `derived`
3. **field cited** — the column, spelled as the CSV spells it
4. **as of** — retrieval time
5. **transformation** — both the original and the resolved string
6. **inverse link** — the locator, which the plain-text export also carries

A **derived** value cites no line. A contribution appears in no file, so a
locator beside it would point at a row holding a different number.
`Citation.__post_init__` refuses to construct either mistake.

Merges are shown **before** they are asked about; contradictory records render
side by side and **are never resolved**; a bare count of sources is never
rendered.

`_provenance` **raises** on a file `sources.csv` does not describe, rather than
rendering a blank as-of. That is why `recovery_inputs.csv` and the other optional
files are not cited in the evidence panel: no dataset here describes them.

---

## 6. The decision log

Append-only, on disk, in `decisions/decisions.jsonl` — gitignored, because it is
operator data containing reviewers' names.

- **Structured, never prose.** The renderer owns the wording and golden files
  pin it; a sentence on disk would fork the first time a word changed.
  `GET /api/decisions` renders on read, so a rewording reaches every entry ever
  recorded.
- **A malformed line raises** rather than being skipped.
- **An unchanged repeat is refused across sessions.**
- **No undo, no delete.** A changed mind is a new entry citing the old one.
- The reviewer's name is **not** persisted server-side.

Override with `SEA_DECISIONS_DIR`; `SEA_RUNS_DIR` does the same for the run
store. The test suite redirects both — without that, running the tests appends a
fixture's decision to the operator's real record.

---

## 7. The API

`src/api/`. A wrapper, and deliberately nothing more: **no threshold, no default,
no coercion, no fallback value.** Every judgment has a home one layer down, and
an HTTP layer is the most tempting place to put a second one.

| endpoint | does |
|---|---|
| `POST /api/score` | scores an upload or a named dataset; `criticality` scopes it |
| `GET /api/run/{id}` | a previous run, **re-scored from its stored inputs** |
| `GET /api/changes` | two runs compared |
| `GET /api/runs` · `GET/POST /api/decisions` | the run list, the log |
| `GET /api/health` | liveness. The one endpoint a key never gates |

### 7.1 Three things the transport is careful about

**A run is re-scored, never replayed.** The run store holds the input CSVs and a
digest of each, and no prose. A wording change reaches a run recorded last month,
and a scoring change shows up as a changed answer rather than a record quietly
disagreeing with the code that claims to have produced it.

**Nothing is rounded on the way out.** `Fraction(73, 2)` crosses as
`{"type":"exact","numerator":73,"denominator":2}`. `null` and `0` stay distinct.
`UNBOUNDED` crosses as `{"type":"unbounded"}`. Every non-plain value is **tagged**,
because a `(quoted, p95)` pair and a rational are both two integers and the
renderer separates them by branch order — which a caller holding only the payload
cannot do.

**The wrap changed no answer, and that is proved rather than asserted.**
`tests/test_api.py` scores the frozen set in process *and* through the transport
and compares all 2072 results on value, unit, completeness, autonomy and reasons,
plus every rendered sentence.

### 7.2 The input contract

`src/contract.py`. Checked before anything is read, and it **raises** rather than
scoring what it can. Every problem names the file, the column, the row where
there is one, and what the column should hold.

- **Never coerce.** A cell that should be a whole number and is not is named with
  its value quoted.
- **Units are part of the contract**, and the rule is *general*: a supplied header
  sharing a stem with a required one and ending in a different recognised unit is
  the right measure in the wrong unit. The refusal also says that renaming the
  header would score weeks as days silently.
- **An ignored column is a notice, not silence** — and it survives a *successful*
  run, because that is the only moment the user reads it.

### 7.3 Authentication

`SEA_API_KEY` is optional. Unset, everything is open — what you want locally and
what every test runs against. Set, every endpoint except `/api/health` requires
it. One rule with one exception, because "which endpoints are safe to expose" is
a judgment that has to be remade every time one is added.

**A static frontend cannot hold a secret.** `web/app/api/[...path]/route.ts` is a
server-side proxy holding the key and forwarding the backend's status and body
**verbatim** — every refusal is a sentence somebody needs to read.

This is a lock on the door, not a register at reception: no accounts, no
sessions, no roles, and `decided_by` is still whatever the reviewer typed.

---

## 8. The interface

Next.js App Router, IBM Carbon v11, **Gray 10**. Six surfaces in the rail.

| surface | job | row is |
|---|---|---|
| Overview | the shape of the whole set. Decides nothing | — |
| Exposure | what is worst | a part |
| What to check | what one fetch settles the most | a **field** |
| Review | judgments waiting for a person | a cluster |
| What changed | two runs compared | a change |
| Decision log | who decided what, when, why | an event |

**Why Carbon.** Every competitor leads with a branded composite index. This
tool's thesis is refusing to combine, so the interface has to make that refusal
read as a position rather than an unfinished feature.

**Non-negotiables**, because violating one is what makes it read off-brand: 0px
radius everywhere, IBM Plex Sans, one accent (`#0f62fe`), surfaces `#ffffff` and
`#f4f4f4`, no shadows, 8px grid. **One documented restyle:** Carbon ships `Tag`
at a 16px radius, which is a pill; `globals.scss` squares it and touches nothing
else about the component.

**One chart is not Carbon.** The region map uses the same library the tested
Streamlit implementation uses, because its geometry carries a decision already
made and asserted — see §9.3. Everything else is `@carbon/charts-react`.

**Three kinds of unknown, three treatments**: fetchable is a warm-grey tag; a
question that does not attach is cool-grey; a threshold nobody configured is an
info notification naming the file and the key. Nothing renders as zero, blank or
a dash.

**Detail opens in a Tearsheet**, never a navigation: the reader is working a list
and sending them away loses their place on every part they look at.

---

## 9. Data

### 9.1 Five directories, five rules

| | |
|---|---|
| `evals/` | **frozen and gated.** Never regenerated. Correctness is measured against this and nothing else |
| `data/` | gitignored, regenerated from seed 42 |
| `demo/` | committed for display only. **Never read by the harness or any test** |
| `template/` | empty files with correct headers, **generated from the contract** and asserted against it |
| `sample/` | a labelled worked example, and the only dataset where the optional files produce figures |

`eval_build.py` is the **only** file allowed to import the generator, and a test
asserts the harness cannot reach it even transitively.

The `demo/` rule is enforced by path: no test may name that directory. When you
find yourself wanting an exception because your test "reads shape, not contents",
that is precisely the argument the rule exists to refuse — I tried it and removed
the test instead.

### 9.2 Provenance

`sources.csv` is the extract manifest: one row per input file with its system of
record and retrieval time. It does not describe itself. Times come from a
declared anchor, never a clock. Lags are **staggered on purpose** — five files
pulled at one instant make "as of" a constant, and a constant is decoration.

### 9.3 The India boundary

`assets/india-claimed.geojson` — India including Jammu & Kashmir, Ladakh, Aksai
Chin, the Shaksgam Valley, Pakistan-administered Kashmir and Arunachal Pradesh.

The built-in `IND` polygon follows Natural Earth, stops near 35.5°N, and ships
inside the chart library where no option reaches it. Source
[datameet/maps](https://github.com/datameet/maps) under **CC BY 4.0**, simplified
by `tools/simplify_boundary.py` from 10.5 MB to 45 KB. Attribution is rendered
beneath the map, not only filed in `assets/README.md`.

Drawn as its own trace **after** the ISO-3 one, so it paints on top. Served from
the one copy by `GET /api/assets/india-claimed.geojson`, so the test that asserts
its **extent** can see every copy there is.

---

## 10. The gate

`python eval_harness.py`. Three layers plus a snapshot.

**Gated floors:** verdict accuracy, name-match precision and recall, abstention
sets, autonomy integrity, BOM structural guarantees, unit integrity, renderer
coverage.

**Never lower a floor to pass.** Each carries its derivation and what would have
to be true for it to be wrong, so changing one edits its justification in the
same commit.

The **snapshot** is explicitly not a floor: those counts are produced by the
system under test, so nothing there blocks a merge.

**883 tests, 4 strict xfails, no skips.** Notable suites:

| | |
|---|---|
| `test_scoring.py` | no composite, every measure keeps its unit |
| `test_binding.py` | states compared, magnitudes never |
| `test_verdict_table.py` | one test per row, expectations hand-written |
| `test_contract.py` | the refusals an enterprise actually meets |
| `test_changes.py` | the four ways a diff lies |
| `test_api.py` | the wrap changed no answer |
| `test_evidence_anatomy.py` | a citation can be *followed* |
| `test_design_properties.py` | colour claims as measurements, never notation |
| `test_rendered_page.py` | what the browser actually painted |
| `test_eval_integrity.py` | the harness cannot reach the generator |

CI runs two jobs: `gate` (Python, with `RENDER_CHECKS=required`) and `web`
(typecheck + build). `main` requires `gate` with `enforce_admins` on.

---

## 11. Known gaps

Marked `xfail(strict=True)`, so closing one **fails the gate** until the marker
is rewritten. A gap cannot be closed silently.

| Gap | Why |
|---|---|
| fractional quantities | the generator emits whole pieces only |
| sub-tier visibility stops one hop down | the schema says where a supplier buys, not where *they* buy |
| in-house concentration | a part made on one internal line is not modelled |
| the resourcing chain is per part, not per candidate source | nothing represents a candidate |

**Two of these replaced closed gaps**, and the pattern is worth knowing: a gap
does not usually vanish, it moves one layer down. Tier correlation was
*unrepresentable* until one optional field made it computable; qualification time
was unrepresentable until the resourcing chain arrived. Both closures rewrote the
xfail rather than deleting it.

Structurally unreachable in seed 42, documented in `docs/EVAL_SCENARIO.md`:
supplier-only concentration, the merge-uncertain exception lane, bounded and
contingent clusters.

**No test runner in `web/`.** The duplicate-key defect in §13.7 was caught by a
dev overlay, not by anything in CI, and the same is true of the measure decoder,
the CSV escaping and the change grouping. This is the largest untested surface
in the project.

---

## 12. Out of scope, by design

Cost optimisation, supplier scorecarding, negotiation support, resourcing
workflow, supplier qualification. If a change starts pulling one of these in,
stop and say so instead of building it.

`annual_spend_usd` is **display-only and unscored**. `committed_at_risk` counts
**promised units, not money**, and the line is deliberate: revenue at risk is a
near neighbour of the cost optimisation agent's job.

---

## 13. What will bite you

1. **Branch, push, PR, merge.** `main` requires the `gate` check with
   `enforce_admins` on, so a direct push of a fresh commit is refused.
2. **Use `.venv`, not `venv`.** Both exist; `venv/` lacks plotly, so the gate is
   red there for purely environmental reasons and the failure text does not say
   so until you open the captured stderr.
3. **Never run `npm run build` while the dev server is up.** They share `.next`,
   so the running page starts serving production bundles, throws minified React
   hydration errors and renders an empty `<main>`. It looks exactly like a code
   regression — it once presented as a missing `RegionMap.tsx` that was on disk
   the whole time. Stop the server, `rm -rf web/.next`, then build.
4. **`NEXT_PUBLIC_*` is inlined at build time.** Setting one in a dashboard does
   nothing until something redeploys: the setting looks correct and the page
   stays broken, and nothing connects the two. `SEA_API_URL` and `SEA_API_KEY`
   are read by the proxy at request time, which is why they are the mechanism.
5. **Verify the rendered page, not the stylesheet.** Four defects shipped that
   every source-reading test passed. A declaration is not a painted pixel, and
   nothing that reads this repository can tell the two apart. Carbon does this
   too: `body.cds--g10` is a class and beats a bare `body`, which printed a grey
   slab on every page of the PDF.
6. **Restart Streamlit after editing `src/`.** Imported modules are cached; stale
   code throws phantom errors that look like real bugs.
7. **Two implementations of one question will disagree, and the one nobody looks
   at is the one that drifts.** The printed summary re-walked the archetype
   layers without de-duplicating and listed fourteen parts twice. Same shape:
   the nav label and the page title were two copies of one name, and renaming one
   timed out every rendered-page check.
8. **Never delete a failing test to go green.** Mark the gap, list it in §11.
9. **A test that reads a literal hex will fail on a correct change.** Assert the
   measured property. The same applies to counting `**` to count headings — that
   proxy broke on a paragraph that used emphasis.
10. **Chase the flake.** A rendered check failed and passed on a retry of the
    same commit; the cause was a wait satisfied before the geo subplot painted.
    "It passed the second time" is how a gate stops being believed.
11. **A scan that refuses a concept by name will contain that name in its
    refusal.** When `tier` became a legitimate grouping basis, the right move was
    to narrow the guard to the declared forms, not to delete the word from the
    list and leave nothing watching for `TIER_HIGH`.
12. **A source scan cannot see what the component library injects, and its
    silence reads as a clean bill of health.** DESIGN.md's Motion section was
    marked `[SHIPPED]` with "zero animations, verified by source scan" while the
    loading state pulsed on a 3s infinite loop on all six surfaces, because
    `SkeletonText` and `SkeletonPlaceholder` carry `animation: … cds--skeleton`
    from inside Carbon. Item 5 is the same lesson in the direction where the
    repository declares something the page ignores; this is the direction where
    the page paints something the repository never declared. **The pulse is
    still there and is now allowed** — the owner permitted it the same day, so
    what was wrong was never the animation, it was a document claiming to have
    checked something it had not.
13. **A deployed container is not the repository.** `assets/` was committed and
    never copied by the Dockerfile, so the map endpoint 404d on every deployed
    page while every test passed: locally and in CI the whole repository is the
    working directory, so the read always succeeds. Run the app against a
    directory holding only what the Dockerfile copies before trusting a deploy.
14. **A host can stop honouring a guarantee the code still keeps.** Render's free
    plan cannot attach a disk, so `SEA_DECISIONS_DIR` is emptied on every
    spin-down and the decision log does not survive. `governance/store.py` is
    unchanged and still correct. Read `render.yaml` before citing the live
    deployment as evidence of persistence.

---

## 14. Deploying it

**It is deployed, as of 2026-09-16.**

| | where | what to know |
|---|---|---|
| frontend | https://supplierexposure-lakshya-jains-projects-05564aa5.vercel.app | Vercel, root directory `web/`. Deployment Protection is **off**, which is deliberate: on, the link opens a sign-in page for an account the recipient does not have |
| backend | https://supplier-exposure-api.onrender.com | Render, **free plan**. Sleeps after 15 minutes idle and wakes on the request, taking about a minute |

`/api/health` on either address answers without a credential and says which
datasets that deployment can see. It is the fastest way to tell "nothing is
listening" from "listening, and it refused", which is the distinction
`web/app/api/[...path]/route.ts` exists to report and used to get wrong.

The frontend is static and goes on Vercel from `web/`. The backend is a
container and goes somewhere that **stays awake** — `fly.toml` pins a plan that
does not scale to zero and mounts a volume at `/data`.

`render.yaml` did too until 2026-09-16, when the owner moved it to the free
plan deliberately. It sleeps after fifteen minutes and loses its decision log on
every spin-down, and it was still the right free option because it **wakes on
the request**, where Streamlit Community Cloud makes the visitor press a button.
The file states what was given up at the line that changed; read it before
citing this deployment as evidence of anything about persistence.

Three things catch people out, in the order they do:

1. **Vercel Deployment Protection is on by default**, so the link you send opens
   a sign-in page for an account the recipient does not have. That is the same
   dead link this whole move was meant to fix.
2. **Set `SEA_API_URL` and `SEA_API_KEY` without a `NEXT_PUBLIC_` prefix**, or
   you publish the key to every visitor.
3. **`/data` must be a volume**, and Render's free plan cannot attach one.
   A decision log that resets is the defect `governance/store.py` exists to
   close, one layer out. Fly mounts one; the free Render service does not have
   the option, which is the accepted cost recorded in `render.yaml`.
