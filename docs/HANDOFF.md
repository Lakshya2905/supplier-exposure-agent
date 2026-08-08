# Handoff

Everything the site does, why it does it that way, and what will bite you.

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
five dimensions it keeps separate, and hands a person a sentence they can act on.

Agent 3 of a multi-agent supply chain system. **Synthetic data only** — no real
part numbers, no real supplier names, nothing company-specific.

The interesting part is not the analysis. It is the set of things the system
declines to do, and the fact that each refusal is enforced by a test rather than
by a convention.

## 2. Running it

```bash
pip install -e ".[dev]"
```

```bash
python -m src.generate_data --seed 42
```

```bash
streamlit run review_app.py
```

Tests and the ship gate:

```bash
python eval_harness.py
```

The gate is the definition of done. It blocks on a failing test, a *passing*
xfail, a manifest mismatch, or a missed floor. `SHIP GATE: PASS` or the task is
not finished.

For the browser checks you also need a browser once:

```bash
python -m playwright install chromium
```

---

## 3. The surfaces

Navigation is a segmented control across the top. There is no sidebar.

### 3.1 Dashboard — *the shape of the whole set*

The landing surface. **No row entity, and it decides nothing** — which is why
adding it did not breach "three surfaces, never one table".

- **Four figure tiles**, each with its denominator. No `delta`: there is no
  previous run, and an arrow pointing at a number that does not exist is worse
  than no arrow.
- **Region choropleth.** The dataset has four regions and no coordinates;
  countries are a **drawing convention**, stated above the map. India is drawn
  from vendored geometry including its full claimed territory — see §7.3.
- **Five small multiples**, identical geometry, five separate axes. One
  dimension per chart, each in its own unit.
- **Supplier-to-part incidence grid**, binary.

### 3.2 Exposure — *what is worst*

Row entity: **a part**. Everything here executes; nothing has a button.

- **Coverage panel first.** What the system does not know leads, because it is
  the most distinctive property of the tool and invisible below the fold.
- **Patterns**: the archetype lattice. Vertical position means dominance;
  horizontal position means nothing and says so. Every group panel is the same
  width regardless of how many siblings its layer holds.
- **Findings**: one per exposed part, in an order declared arbitrary. A part in
  several archetypes is explained **once**.
- **Evidence** under each finding — see §5.
- **Blocking matrix**: which finished goods each part can stop, as identical
  marks.
- **Region filter** on the findings, with the hidden count stated on screen.

### 3.3 Find out — *what should I go and get*

Row entity: **a field**, not a part. One row is one trip to one system of
record, which is what makes it a work queue rather than a list of parts.

Ranked by how many parts each field would settle — and that ranking is
deliberate, because "which single trip settles the most" is the question this
surface asks.

### 3.4 Confirm — *do I agree with your model*

Row entity: **a cluster**. One cluster is one act, so `member_count` carries the
size rather than the surface repeating the judgment per member.

- **Decisions recorded** leads the surface.
- **Cluster sizes**, coloured by grouping basis — supplier and region are not
  rivals (§4.4).
- **Who sits with whom**: identifiers only.
- Per cluster: the finding, Confirm / Reject, a reason code, a note, and **any
  decision already standing against it**.

### 3.5 The standing strip

Under the navigation, on **every** surface. Each of these was previously
reachable from exactly one page:

| | |
|---|---|
| **Your name** | required — an anonymous decision is refused |
| **Decisions recorded (n)** | the full log |
| **Not assessed (n)** | the coverage sentences |
| **Data and run** | which systems were read and when |

---

## 4. The analysis

### 4.1 The autonomy ladder — this is the product, not a detail

| Level | What |
|---|---|
| **Executes** | explosion, the supplier join, exposure identification, the four per-part dimensions where inputs exist |
| **Recommends** | correlation and concentration flagging — a human confirms |
| **Recommends permanently** | concentration grouping and the archetype catalogue |
| **Never** | supplier qualification. Out of scope by design |

**Autonomy is an affordance, never an appearance.** An executed finding has
nothing to click. `Row.__post_init__` refuses to construct an executed row
carrying a control, so the claim survives a restyle.

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

### 4.3 The five dimensions

| Dimension | Unit |
|---|---|
| `lead_time_to_recover` | days — a `(quoted, p95)` pair |
| `blast_radius` | finished-good units |
| `buffer_cover` | days |
| `portability` | categorical |
| `concentration` | parts |

**They are never combined.** No total, no weight, no `__add__`, and no
normalised variant of any value. Every measure keeps a physical unit, because a
unitless number in a fixed range is a composite already assembled.
`tests/test_scoring.py` enforces this and did not change when charts arrived.

A chart may draw one dimension in its own units. **Nothing puts two dimensions
on one axis** — which is why there is no radar or parallel-coordinates plot.

### 4.4 Two kinds of disagreement

The test is one question: **could any fact settle it?**

- **Settleable** → uncertainty → routes to a lane with both readings and the
  evidence that would settle it.
- **Unsettleable** → structure → reported as the finding.

Supplier-grouping versus region-grouping cannot be settled by any fact anybody
could go and find, because it is not a question about the world. Routing it to a
lane would bury a real result among things that look like errors.

### 4.5 Abstention is a first-class output

Six states, and no two collapse: `known`, `upper_bound`, `lower_bound`,
`cannot_tell`, `no_recovery_path`, `not_applicable`. Only `cannot_tell` routes
for review.

**Missing and zero are different facts.** A blank on-hand means *no record* and
never reads as zero; a recorded zero is real. Absence is never dimmed, never
blank, never a dash — it renders at the same weight and footprint as an asserted
value.

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

Also: merges are shown **before** they are asked about (an inline sigil outside
the expander); contradictory records render side by side and **are never
resolved**; a bare count of sources is never rendered; the record exports as
plain text.

---

## 6. The decision log

Append-only, on disk, in `decisions/decisions.jsonl` — gitignored, because it is
operator data containing reviewers' names.

- **Structured, never prose.** The renderer owns the wording and golden files
  pin it; a sentence on disk would fork the first time a word changed.
- **A malformed line raises** rather than being skipped. A silently dropped
  decision is the trail lying by omission.
- **An unchanged repeat is refused across sessions**, because the log survives a
  reload.
- **No undo, no delete.** The panel carries no control.
- The reviewer's name is **not** persisted: who is at the keyboard is a fact
  about now.

Override the location with `SEA_DECISIONS_DIR`. The test suite does, per test —
without it, running the tests appends a fixture's decision to the operator's
real record.

---

## 7. Data

### 7.1 Three directories, three rules

| | |
|---|---|
| `evals/` | **frozen and gated.** Never regenerated. Correctness is measured against this and nothing else |
| `data/` | gitignored, regenerated from seed 42 |
| `demo/` | committed for display only. Never read by the harness or any test |

`eval_build.py` is the **only** file allowed to import the generator, and a test
asserts the harness cannot reach it even transitively. Eval floors are never
produced by the generator under test.

### 7.2 Provenance

`sources.csv` is the extract manifest: one row per input file with its system of
record and retrieval time. It does not describe itself. Times come from a
declared anchor, never a clock — a wall-clock stamp could never be rebuilt and
checked against itself.

Lags are **staggered on purpose**. Five files pulled at one instant make "as of"
a constant, and a constant on every record is decoration.

### 7.3 The India boundary

`assets/india-claimed.geojson` — India including Jammu & Kashmir, Ladakh, Aksai
Chin, the Shaksgam Valley, Pakistan-administered Kashmir and Arunachal Pradesh.

Plotly's built-in `IND` follows Natural Earth, stops near 35.5°N, and ships
inside plotly.js where no option reaches it. Source
[datameet/maps](https://github.com/datameet/maps) under **CC BY 4.0**, simplified
by `tools/simplify_boundary.py` from 10.5 MB to 45 KB. Attribution is rendered
beneath the map, not only filed in `assets/README.md`.

It is drawn as its own trace **after** the ISO-3 one, so it paints on top. Tests
assert the **extent**, not the file.

---

## 8. The gate

`python eval_harness.py`. Three layers plus a snapshot.

**Gated floors:** verdict accuracy, name-match precision and recall, abstention
sets, autonomy integrity, BOM structural guarantees, unit integrity, renderer
coverage.

**Never lower a floor to pass.** Each carries its derivation and what would have
to be true for it to be wrong, so changing one edits its justification in the
same commit.

The **snapshot** section is explicitly not a floor: those counts are produced by
the system under test, so nothing there blocks a merge.

**719 tests.** Notable suites:

| | |
|---|---|
| `test_scoring.py` | no composite, every measure keeps its unit |
| `test_verdict_table.py` | one test per row, expectations hand-written |
| `test_evidence_anatomy.py` | a citation can be *followed* |
| `test_design_properties.py` | colour claims as measurements, never notation |
| `test_rendered_page.py` | what the browser actually painted (§9) |
| `test_eval_integrity.py` | the harness cannot reach the generator |

## 9. The rendered-page checks

**Four defects shipped that every source-reading test passed.** They are one
failure, not four: *a declaration is not a painted pixel*, and nothing that reads
the repository can tell the two apart.

`tests/rendered.py` serves the app to headless Chromium and reads
`getComputedStyle`. Required in CI via `RENDER_CHECKS=required`; skipped locally
without a browser — and `eval_harness.py` prints every skip under **"DID NOT RUN,
and the gate is green anyway"**, because a control that skips quietly is worse
than no control.

---

## 10. Design system essentials

Full contract in `DESIGN.md`. Two rules there are correctness constraints, not
preferences:

- **Never state a perceptual guarantee in HSL.** Use OKLCH or CIELAB and assert
  the measured property.
- **Absence is never dimmed, never zero, never blank.**

Substrate is **light** since 2026-08-07. The ramp was not inverted — each step
was solved for the contrast its dark counterpart held.

**The encoding rule was retired by the owner on 2026-08-06**, deliberately and on
the record. Charts, a choropleth and RAG colouring are permitted. The objection
was *overruled, not refuted*, and what it cost is written down. **The arithmetic
rule is untouched.**

---

## 11. Known gaps

Marked `xfail(strict=True)`, so closing one **fails the gate** until the marker
is removed. A gap cannot be closed silently.

| Gap | Why |
|---|---|
| fractional quantities | the generator emits whole pieces only |
| tier correlation | unrepresentable: the data has no tier |
| in-house concentration | a part made on one internal line is not modelled |
| qualification time in lead-time-to-recover | the data carries quoted lead time, not time to qualify an alternative |

Structurally unreachable in seed 42, documented in `docs/EVAL_SCENARIO.md`:
supplier-only concentration, the merge-uncertain exception lane, bounded and
contingent clusters.

Still open in the interface: the merge sigil renders but is not itself a target;
`sources disagree` has no chip because seed 42 produces no contradiction; the
typography faces are specified but not vendored.

## 12. Out of scope, by design

Cost optimisation, supplier scorecarding, negotiation support, resourcing
workflow, supplier qualification. If a change starts pulling one of these in,
stop and say so instead of building it.

`annual_spend_usd` is **display-only and unscored**. Ranking by it is the cost
optimisation agent, not this one.

---

## 13. What will bite you

1. **Restart Streamlit after editing `src/`.** Imported modules are cached; stale
   code throws phantom errors that look like real bugs.
2. **Verify the rendered page, not the stylesheet.** Streamlit wins specificity
   fights you did not know you were in. Three dead selectors have shipped:
   `stVerticalBlockBorderWrapper`, `data-baseweb` attributes, and
   `stSegmentedControl` (it is `stButtonGroup`).
3. **Branch, push, PR, merge.** `main` requires the `gate` check with
   `enforce_admins` on, so a direct push of a fresh commit is refused.
4. **Never delete a failing test to go green.** Mark the gap, list it here.
5. **A test that reads a literal hex will fail on a correct change.** Assert the
   measured property.
6. **Chase the flake.** A rendered check once failed and passed on retry; the
   cause was a wait satisfied by the *previous* surface. "It passed the second
   time" is how a gate stops being believed.
7. **`st.code`, `st.dataframe` and plotly paint their own defaults.** The
   dataframe is a canvas and CSS cannot reach it — it prints in screen colours,
   and that limit is stated rather than papered over.
