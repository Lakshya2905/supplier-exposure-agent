# Design System, Supplier exposure

> ## THIS IS A TARGET, NOT A DESCRIPTION
>
> **The app does not currently satisfy this document.** Read every section as what
> the interface should become, never as a report on what it does.
>
> Sections are marked:
>
> - **`[SHIPPED]`** the app matches this today, verified by measurement against the running app.
> - **`[TARGET]`** specified here, **not implemented**. Nothing in the app satisfies it yet.
> - **`[PARTIAL]`** some of this ships; the section says which part does not.
>
> **A `[TARGET]` guarantee is not in force.** Do not cite a `[TARGET]` number as
> evidence that the app is accessible or that any rule here is enforced. Typography,
> spacing, evidence anatomy, focus indicators and print are all still targets.
>
> **Correction, 2026-08-05.** An earlier draft of this header claimed two chips
> failed WCAG AA in the running app. That was wrong. Nine of the eleven hues never
> reached a badge, so the two failing values (`not_applicable` 4.43:1, `region`
> 4.41:1) were dead code paths. The only hue that ever rendered was `executes` at
> 5.21:1, which passes. The palette defect was a **latent trap**, not a live
> accessibility failure, and it is now removed.

**Measurement provenance.** Every number here was computed against the running app
or against the specified colour values, not estimated. Contrast ratios are WCAG
2.1 relative luminance. Lightness and chroma are CIELAB and OKLCH, never HSL, for
reasons the Color section explains. The arithmetic is deterministic and any reader
can reproduce it.

**Substrate caveat, applies to every contrast and equality figure in this file.**
All of them are measured on the dark substrate (`#14171A` page, `#191D21` panel).
**None of them transfer to white paper or a light theme.** A light or print variant
voids every guarantee in this document until the numbers are re-measured on that
substrate. See Print.

**Review provenance, single model.** The perceptual finding in the Color section
(that the HSL equality claim was false, and the CIELAB measurements behind it) was
reviewed only by a second Claude instance, not by a genuinely independent model.
Codex was unavailable. Two Claude instances disagreeing is not cross-model review,
and that qualifier stays attached to the finding permanently rather than being
dropped in a later summary. The underlying arithmetic is reproducible and does not
depend on any model; the design conclusion drawn from it does not carry
independent corroboration.

## Product Context

- **What this is:** an internal review tool that answers which single points of failure in a bill of materials would actually stop production.
- **Who it's for:** supply chain analysts and procurement reviewers doing careful, high consequence work.
- **Space:** supply chain risk and procurement analytics. Peers sell composite risk scores; this tool refuses to compute one.
- **Project type:** internal analyst tool, read only, Streamlit 1.61.
- **The one thing to remember:** every claim shows its work. Evidence is the spine of the interface, not a disclosure behind a chevron.

The closest design precedent is not a commercial risk platform. It is the NIST
vulnerability database, which holds three incommensurable scoring systems side by
side without reconciling them, renders "not yet provided" as a first class state,
gives semantically different tags identical visual weight, and cites a source on
every row. That is this product's stance already shipping in a tool people trust
for exactly this kind of decision. This is a reference tool, not a scoring tool.

## Aesthetic Direction [PARTIAL]

> [PARTIAL] Dark, minimal and motionless ship today. The shift in register from monitoring console to instrument record is a target.

- **Direction:** industrial / utilitarian, in the register of an instrument record rather than a monitoring console.
- **Decoration level:** minimal. Typography and alignment do all the work. No texture, no gradient, no glow, no shadow.
- **Mood:** still and unhurried. The page should behave like a document that happens to have a cursor. A reviewer should slow down, not scan.
- **Reference object:** a factual exhibit. Findings stated in prose, every figure carrying a reference back to the row that produced it.
- **First three seconds:** "this is not trying to sell me a conclusion." The first quantity the eye lands on is how much is unknown.

## Typography [TARGET]

> [TARGET] The app runs Streamlit's default Source Sans. None of the three faces below are loaded, and `theme.fontFaces` is not configured.

Type carries provenance. This is the load bearing rule of the whole system.

- **Findings and prose: Literata.** A serif signals document rather than dashboard. Finding sentences are genuinely reading text, set to a 104ch measure, not interface furniture. If it is serif, a person asserted it.
- **UI, headings, labels, chips: IBM Plex Sans.** Designed for technical documentation, excellent at small sizes, real tabular figures.
- **Every value from a data row: IBM Plex Mono.** Part numbers, supplier names, day counts, row ids, file names. If it is mono, a row produced it.

A reviewer learns that rule in ten seconds and then cannot be confused about what
is inference and what is record. Never set a category name or any prose in mono.
Never set a value that came from a source in the serif.

All three are open licensed (SIL OFL), so they can be vendored.

- **Loading:** self host woff2 under `static/` with `server.enableStaticServing = true`, declared through `[[theme.fontFaces]]` in `.streamlit/config.toml`. Do not load fonts from a third party CDN: an audit tool must not depend on a network fetch to render its own record, and a CDN outage must not change how a finding reads.
- **Config, not CSS.** Streamlit 1.61 supports `theme.fontFaces`, `theme.headingFont`, `theme.codeFont`, `theme.baseFontSize`, `theme.headingFontSizes` and `theme.headingFontWeights`. Type belongs there, versioned, not in the `CONSOLE_CSS` string.
- **Tabular numerals are mandatory** anywhere figures stack: `font-variant-numeric: tabular-nums`.

### Scale [TARGET]

> [TARGET] Ten font sizes ship today with step ratios from 1.012 to 1.426. The five below replace them.

Five sizes, replacing the ten that exist today (whose step ratios ranged 1.012 to
1.426, which is not a scale). Two zones, stated honestly rather than pretending one
ratio governs a dense console.

| Step | Size | Face | Used for |
|------|------|------|----------|
| `ui-xs` | 12px | Plex Sans 500 | chip labels, captions |
| `ui-sm` | 13px | Plex Sans / Plex Mono | notes, table cells, identifiers |
| `ui-base` | 14px | Plex Sans 600 | h2 (uppercase, 0.08em), h3 to h6 |
| `doc` | 15px | Literata 400 | finding sentences, the reading size |
| `title` | 21px | Plex Sans 600 | h1, one per surface |

Minimum text size anywhere is 12px. Never set a multi word label in uppercase mono
below 12px: all caps removes word shape and forces letter by letter reading, which
is the slowest mode applied to the densest label.

## Color

### The rule this system got wrong, and the correction [SHIPPED]

> [SHIPPED] The defect described here is **fixed** as of `282657a`. It is kept in
> full because the shape of the failure is the transferable part.
>
> **Severity correction.** This was a latent trap, not a live defect. Nine of the
> eleven hues never reached a badge; only `executes` rendered a coloured fill, and
> its label passed WCAG AA at 5.21:1. So no reader ever saw the ordered ramp. What
> made it worth fixing is that the first caller to write `badge(row.completeness)`
> would have shipped one, with three guards reporting that the palette could not
> rank.

`config.toml`, the `.badge` CSS rule, and `test_the_category_palette_is_nominal_by_arithmetic`
all asserted that every chip shares one saturation and one lightness, therefore
"no chip is darker, stronger or warmer than another, so no reading of the set
produces an order."

That claim was stated in HSL, and HSL lightness is not perceptual lightness.
Measured in CIELAB, the six completeness chips spanned **15.3 L\* points** and
sorted into a clean brightness ramp, lightest `not_applicable` (L\* 43.7) down to
darkest `lower_bound` (L\* 28.4), with chroma varying more than twofold. The eye
saw an order the arithmetic denied.

**Single model caveat, permanent.** This finding was reviewed only by a second
Claude instance. Codex was unavailable, so there is no genuinely independent
model check on it. Two Claude instances disagreeing is not cross-model review.
The arithmetic is deterministic and reproducible by anyone; the design conclusion
drawn from it (retire category hue) does not carry independent corroboration.
Keep this qualifier attached wherever the finding is repeated.

### The general form of the failure

Three independent mechanisms enforced this guarantee and all three checked
notation rather than the property:

1. `.streamlit/config.toml` asserted it in a comment, in HSL terms.
2. The `.badge` CSS rule declared one background and one colour, which inline
   styles then overrode per category.
3. `test_the_category_palette_is_nominal_by_arithmetic` asserted equal HSL
   saturation and lightness strings, and passed.

**Redundant guards that share an assumption read as confirmation while providing
none.** Three checks agreeing looked like triangulation. It was one check
performed three times, because all three inherited the same wrong premise, that
HSL lightness is perceptual lightness. Independence is not about how many guards
exist or where they live; it is about whether they can fail separately. Guards
that share a premise fail together and silently, and their agreement is the thing
that makes the failure hard to see.

This is a sharper form of testing the wrong thing. Testing the wrong thing leaves
you with no evidence. Redundantly testing the wrong thing leaves you with false
evidence, which is worse, because the count of passing guards is what stops
anybody looking. When adding a guard, ask what premise it shares with the guards
already there. If the answer is "the same one," it adds confidence without adding
coverage.

**Never state a perceptual guarantee in HSL.** Use OKLCH or CIELAB, and assert the
measured property, not the notation.

### Surfaces [SHIPPED]

> [SHIPPED] Verified against the running app. Every value passes WCAG AA.

Unchanged. This part of the system is well built and every value below passes
WCAG AA, several above 12:1.

| Token | Hex | Use |
|-------|-----|-----|
| `bg` | `#14171A` | page |
| `surface` | `#191D21` | bordered panel |
| `surface-head` | `#1E242A` | panel header strip |
| `surface-sidebar` | `#101315` | sidebar |
| `border-hairline` | `#262B30` | dividers, table rules |
| `border-panel` | `#272D33` | panel edge |
| `border-ui` | `#6B7278` | anything whose boundary must be identifiable (3.47:1 on surface, 3.69:1 on bg) |

### Text ramp, with the semantic mapping [PARTIAL]

> [PARTIAL] The six colours and their ratios ship and are verified. The semantic mapping (when a note applies versus a caption) exists only here; nothing enforces it.

Five greys with no usage rule will be chosen by feel and drift within a week, so
the rule is part of the system.

| Token | Hex | On bg | Means |
|-------|-----|------:|-------|
| `text-title` | `#F0F2F4` | 16.03:1 | h1 only |
| `text-primary` | `#E3E6E8` | 14.35:1 | a finding, the thing you came to read |
| `text-body` | `#D5DADE` | 12.78:1 | prose, chip labels, absence states |
| `text-note` | `#9BA3AA` | 7.04:1 | a qualification attached to a finding |
| `text-caption` | `#838C94` | 5.26:1 | instructions about the interface, never about the data |
| `text-section` | `#8FA0AD` | 6.68:1 | h2 section labels |

`text-note` and `text-caption` are not interchangeable. A note is about the data.
A caption is about the interface. If it would still be true with different data,
it is a caption.

### The accent contract [PARTIAL]

> [PARTIAL] Accent usage and every ratio below ship and are verified. The requirement that colour never be the only cue for actionability (WCAG 1.4.1) is a target.

- **`accent` `#7FB2D9`**, 7.94:1 on bg, 7.48:1 on surface, 6.91:1 on panel head.
- The accent marks **only** what a reviewer can act on or navigate to: links, expander summaries, the active nav rule, button borders, and the outlined autonomy chip (which is exactly the `recommends` state, the one that gets a Confirm and Reject button).
- The accent is **never** applied to a finding, a part, a dimension, or a category.
- **Colour is never the only cue for actionability** (WCAG 1.4.1). Every actionable element also carries a non colour affordance: an underline, a caret, a bracket, or a border.
- Nothing in the chip vocabulary may land near the accent's hue, `oklch(0.742 0.078 242)`. This is why the category palette does not use hue at all.

### The category chip: one neutral chip, form carries taxonomy [SHIPPED]

> [SHIPPED] Implemented in `282657a` and `9e3c25a`. Verified in a browser: every
> chip renders `#242A30` with `#D5DADE` text at 12px, no inline styles, and the
> absent variant differs from a plain chip only on `border-style`.

Hue is retired from the category palette. `CLAUDE.md` already required this and
the palette was not honouring the spirit of it: **"strip every colour and no
information may be lost."** If that rule holds, hue is redundant by definition.
Eleven hues that vary systematically look like an encoding, so a reader tries to
learn a mapping, and the mapping did not hold up. It carried three unrelated
taxonomies at once (autonomy, completeness, cluster kind), so the same hue meant
different things on different surfaces. Its separation collapsed to ΔE 3.4 under
deuteranopia, giving roughly 8% of male reviewers no signal. A chip would have
landed 12 degrees from the accent, the one colour reserved for "you can act on
this." And hue position tracked enum declaration order, leaking a ranking back
in through the channel the product had just cleaned.

`CLAUDE.md` permits hue to distinguish categories. It does not require it, and
here it costs more than it returns.

| Variant | Spec | Means |
|---------|------|-------|
| solid | fill `#242A30`, 1px `#6B7278`, text `#D5DADE` at **10.29:1** | an asserted category |
| outlined | transparent fill, 1px `accent`, text `accent` at **7.48:1** on surface | this row has a control (redundant with the control, see below) |
| dashed | fill `#242A30`, 1px dashed `#6B7278`, text `#D5DADE` | an absence, see below |

- **Chip fill never carries identification.** Fill sits at 1.08:1 to 1.29:1 against the surfaces behind it. The border and the label do the work.
- Chip label: 12px Plex Sans 500, **sentence case**, 0.02em tracking. Not uppercase, not mono, not below 12px.
- **The outlined variant never carries autonomy.** `CLAUDE.md` is explicit that autonomy is an affordance, never an appearance, because "a styling distinction is one commit from evaporating." The affordance is the presence or absence of a control, enforced in the view model, which refuses to construct an executed row carrying one. The outlined chip is redundant decoration on top of that affordance and must never be the only thing distinguishing the two states. If the chip and the control ever disagree, the control is right.
- Remaining taxonomy is distinguished by position and label, not hue: the section heading a chip sits under, and the words in the chip. Form and position survive greyscale, colour vision deficiency, screenshots pasted into a review memo, and print. Hue survived none of those reliably.
- **A category name is never truncated.** A truncated epistemic state is a wrong claim, not a cosmetic problem. Wrap instead.

## Absence and Uncertainty [PARTIAL]

> [PARTIAL] The chip vocabulary and the never-dimmed rule ship as of `9e3c25a`, for the three kinds the pipeline actually emits. The five-state table below is **not** all implemented: see the note under it.

"I cannot tell" is a first class output, so it gets a first class specification.
This is the section that matters most after Evidence.

**Absence is never dimmed.** An absence renders at `text-body`, the same weight as
an asserted value. Dimming an unknown says it matters less, which is the exact lie
this product exists to refuse. Absence occupies the same footprint as presence:
same chip, same row height, same column. It never collapses to whitespace and
never renders as zero, blank, or a dash.

Absences are not interchangeable and a reader who cannot tell them apart will
collapse them into one shrug. Each is a dashed chip with distinct label text.

**Shipped.** These are the three kinds `coverage()` actually emits, carried on
`CoverageNote.kind` and labelled by `ABSENCE_LABEL` in `review_app.py`:

| Kind | Label | Means |
|------|-------|-------|
| `unplaceable` | `unresolved` | the supplier list is unconfirmed, so membership cannot be settled |
| `not_applicable` | `not applicable` | the question does not attach to this part |
| `no_thresholds` | `not configured` | a threshold nobody has set, and the system will not choose one |

**Reserved, not implemented.** The model cannot currently distinguish these, and
an earlier draft of this document specified them as though it could. Inventing a
label for a state the data cannot tell apart is the interface claiming a precision
the model does not have, so no label exists until the model can produce the
distinction:

| State | Label when it exists | Means |
|-------|----------------------|-------|
| not collected | `no record` | the source has no row for this |
| stale | `as of <date>` | a record exists but predates the as-of horizon |
| conflicting | `sources disagree` | two sources answer differently and neither wins |
| structurally unknowable | `cannot be established` | no source could answer this even in principle |

**An unrecognised kind gets no chip rather than a guessed one**, for the same
reason the palette refuses to invent a colour: a wrong label on an absence is
worse than no label, because the reader would act on it. A test asserts that every
kind the model emits has a label, so a fourth kind cannot render as an
unexplained absence.

Distinct from every absence, and rendered as a **solid** chip because it is an
assertion rather than a gap:

| State | Label | Means |
|-------|-------|-------|
| negative finding | `none found` | the question was asked, the answer is no |

`no record` and `none found` are the pair most often collapsed by mistake. Missing
and zero are different facts. A blank on-hand means no record and must never read
as zero; a recorded zero is real.

**Every panel states its denominator before its numerator.** A coverage line
("4 of 5 dimensions assessed, supplier financials unknown") comes before the
findings, not after. The count of unknowns is set at least as prominently as any
finding.

## Evidence [TARGET]

> [TARGET] **Not implemented.** Evidence today is a collapsed expander with supplier rows, demand rows and a lead time record. None of the anatomy below is a structured contract, and the fuzzy-merge sigil does not exist.

The memorable thing is "every claim shows its work," so evidence is specified in
more detail than the palette.

### Anatomy [TARGET]

> [TARGET] None of these six fields is currently a specified, enforced part of an evidence record.

Every claim resolves to one or more evidence records, and each record carries:

1. **source id** (mono): the file and row that produced the value.
2. **source type**: which system of record, and whether it is authoritative or derived.
3. **field cited**: the exact column, spelled as the source spells it.
4. **as of**: when the record was retrieved.
5. **transformation applied**: any normalisation, unit conversion, or fuzzy name merge, stated with both the original and the resolved string.
6. **inverse link**: from evidence back to the raw record, so the chain is walkable in both directions.

### Rules [TARGET]

> [TARGET] The read-only rule and the no-write-path rule ship. The rest are targets.

- **The evidence view shows the source as the source spells it.** Original column headers, original casing, original whitespace. No relabeling, no realignment to the pretty grid, no unit prettification. If it looked designed, a reviewer would suspect it had been processed.
- **A fuzzy merge is always visible before it is asked about.** A value that survived a name merge carries an inline mono sigil, and the sigil is itself a target: opening it shows both strings and the rule that fired. This is currently buried inside an expander and should not be.
- **Absent evidence is a specified state, not an empty panel.** A claim with no evidence says so in the same vocabulary as the Absence section.
- **Contradictory evidence is shown, never resolved.** Both records render. The tool does not pick.
- **Never render a bare count of sources.** "3 sources" invites reading count as strength, and three weak records do not outrank one authoritative one. Show source identity and type. Never render a tally as repeated marks.
- **Evidence is exportable as plain text**, carrying file, retrieval time, row ids, and every transformation applied, so a citation can be pasted into a review memo intact.

## The Decision Panel [TARGET]

> [TARGET] **Not implemented.** Decisions are recorded and nothing displays them.
> Everything the panel depends on now ships: `render_all` renders one sentence per
> event with committed goldens, a cluster decision states its arity (`7ff6f14`), a
> decision carries a real timestamp (`b898c81`), an unchanged repeat is refused and
> a changed one cites what it replaces (`e6d1a72`). What is missing is the surface.

The Confirm surface records a reviewer's judgments into an append-only log and
shows none of them. `st.success("Recorded: ...")` appears 158px below the control
and is erased by the next decision, so exactly one of 23 judgments has any trace
on screen at any moment.

- **The panel assembles no prose.** It renders `render_all(log)` output. Every
  string it needs that is not an event sentence (heading, empty state, scope line,
  order label) belongs in `render.py` beside `render_coverage_note`, in the section
  that already exists for "wording with no event", golden-pinned with the rest.
  Writing those strings inline in the painter is the shortest path and it makes
  `README.md`'s claim that the interface assembles nothing of its own false.
- **The record is session-scoped and says so in full-weight prose**, not a dimmed
  caption. The log lives in `st.session_state` and is in-memory, so a refresh or an
  idle reap empties it. An emptied log and a fresh session render identically
  unless the wording distinguishes them, which is the `no record` versus
  `none found` collapse the Absence section names.
- **The empty state renders before the first decision**, so a reviewer learns the
  panel exists before they need it. Zero decisions here is a **recorded** zero, the
  reviewer's own count, so a figure is honest.
- **The order is declared.** A linear list of 23 items with no stated order
  violates the anti-ranking contract. Chronological is meaningful for a ledger, so
  this is one caption, not a design problem.
- **No control.** Append-only means no undo and no delete. A button added here also
  shifts `app.button[0]` and breaks the three existing tests that index buttons
  positionally.

### Known trap: `note` is shadowed at the panel's insertion point

**`review_app.py:515` binds `note = st.text_input("Note", ...)` inside
`render_confirm`.** That makes `note` a function-local name for the whole of
`render_confirm`, shadowing the module-level `note()` helper defined at
`review_app.py:277`.

A panel added at the foot of `render_confirm` that calls `note("This record covers
this session only.")` therefore raises:

```
TypeError: 'str' object is not callable
```

and if the surface has no rows, `UnboundLocalError` instead.

**Why this is written down rather than left to be discovered.** The traceback
points at the panel, three lines of new code, and says the call is wrong. The
actual cause is a name binding 40 lines above it that has been correct and
harmless since it was written. Nothing about the error names the collision, and
the first instinct will be to change the panel. Rename the widget local to
`note_text` (and its `note=note` argument at `:528`) in the same commit as the
panel, before writing the panel body.

## The Anti-Ranking Contract [PARTIAL]

> [PARTIAL] Dimensions stay separate, no sort control exists, and the order label now declares the order meaningless as of `f4130e0`. The equal-area rule and the written no-default-sort rule are still targets, enforced by nothing.

The five scoring dimensions stay separate forever. That is a correctness
constraint, and layout can violate it as easily as arithmetic can.

- **Fixed order, declared arbitrary.** The dimensions render in one order, always, and the interface says in words that the order carries no meaning.
- **No dimension gets more area, weight, or colour than another.** Identical geometry is the encoding: the reader compares contents, not sizes.
- **No default sort derived from more than one dimension.** That is a composite score with the number hidden.
- **No sort control on any dimension.** A reviewer who sorts by dimension three has declared dimension three the ranking. Sorting is a smuggled conclusion; filtering is a stated question, so filtering is offered freely. Where a sort control would have been, say why there is none.
- **Reading order is not priority.** If a set must be laid out linearly, say so.
- **The order label stays; the promise of a control goes.** `CLAUDE.md` requires that any default ordering be arbitrary, stable, and labelled in the output, "because a plausible default is read as a ranking." `DEFAULT_ORDER_LABEL` in `src/ranking.py:40` reads "ordered by part number; choose a dimension to rank by". The first clause satisfies that rule and must stay. The second promises a control that does not exist anywhere in the app (0 sort controls, 0 sliders, 0 radios outside navigation) and that this contract says should never exist. Drop the second clause only.

### Banned widgets, and what to use instead [PARTIAL]

> [PARTIAL] The first five rows are enforced by a source scan in `tests/test_review_app.py`. The `st.metric(delta=)`, dataframe-sort and red/amber/green rows are additions here and are not yet enforced.

Every one of these is a normalised scale by construction, which is the composite
arriving through a widget rather than through arithmetic. `tests/test_review_app.py`
scans the source to enforce the list.

| Banned | Why | Instead |
|--------|-----|---------|
| `st.progress`, `ProgressColumn` | a literal 0 to 1 bar | the figure, in mono, with its unit |
| `BarChartColumn`, `LineChartColumn`, `AreaChartColumn` | magnitude as length inside a table | a column of tabular figures |
| `st.bar_chart`, `st.line_chart`, `st.area_chart`, `st.scatter_chart` | shared axis across incommensurable dimensions | small multiples with identical geometry, or a table |
| `background_gradient`, `color_gradient` | ordinal encoding of a heterogeneous set | one neutral chip |
| `st.slider` | a threshold with no owner and no version | a value in `config/archetypes.yaml`, owned and versioned |
| `st.metric(delta=...)` | ships red and green delta arrows, which is RAG plus magnitude | state the two figures and their dates |
| `st.dataframe` column sort | free per column sort supplies a ranking silently | pass explicitly ordered data; disable or ignore column sort |
| red / amber / green anywhere | three stops on one ordered axis wearing a costume | the label, in words |

Green is unavailable even where it looks harmless. No dimension here has a "good":
a part with one qualified supplier is not good, it is concentrated, which may be
fine or fatal depending on the other four dimensions.

## Spacing [TARGET]

> [TARGET] **Not implemented.** 38 distinct rem values ship, 5 of which land on any grid.

- **Base unit:** 4px.
- **Density:** compact. This is an operational console, high information per screen.
- **Scale:** `xs` 4, `sm` 8, `md` 12, `lg` 16, `xl` 24, `2xl` 32, `3xl` 48.

Replaces the 38 distinct rem values currently in `CONSOLE_CSS`, of which 5 land on
any grid. Vertical rhythm between a heading and its content is `sm`; between
sections is `xl`; panel padding is `md`.

## Layout [PARTIAL]

> [PARTIAL] The 104ch measure and the radius scale ship. Adjacent paired actions and the no-mid-token-break rule are targets; Confirm and Reject are currently ~280px apart.

- **Approach:** grid disciplined. Strict alignment, predictable columns, no asymmetry.
- **Measure:** 104ch maximum for prose. Keep it: it is tuned and correct.
- **Max content width:** full, with `xl` page gutters.
- **Border radius:** `sm` 2px for data surfaces, `md` 3px for chips, buttons, alerts, `lg` 4px for panels. No radius above 4px anywhere. Nothing is pill shaped.
- **Paired actions sit adjacent.** Opposing controls (Confirm and Reject) belong next to each other. They are currently separated by roughly 280px of empty column because the control row uses `st.columns(len(controls) + 1)`, which pins each button to the left edge of a one third column.
- **Long identifiers and URLs never break mid token.** Set `word-break: keep-all` on identifiers and links.

## Motion [SHIPPED]

> [SHIPPED] This formalises what already ships: zero transitions, zero animations, zero keyframes, verified by source scan.

- **Approach:** none. This is a formalisation, not a change: the app currently has zero transitions, zero animations, and zero keyframes.
- No entrance animation, no spinner, no pulse, no skeleton. A page that animates while data settles implies the data is moving. It is not; it is a record.
- The only permitted state change is instantaneous.
- If a load is slow enough to need feedback, state it in words.

## Focus and Keyboard [TARGET]

> [TARGET] **Focus indicators are not implemented.** Streamlit defaults are whatever they are and have not been measured. The reviewer-name persistence bullet is the exception: that one shipped in `6d1a8ae`.

- Every interactive element has a visible focus indicator at **3:1 or better** against both the element and the surface behind it (WCAG 2.4.7, 2.4.11). `border-ui` `#6B7278` satisfies this.
- Focus is never indicated by colour alone.
- Tab order follows reading order.
- The reviewer name field must not lose its value on navigation. It sits in the sidebar but is created inside the confirm surface, so Streamlit discards its state on any surface change; hold it in a plain `session_state` slot that no widget owns.

## Print [TARGET]

> [TARGET] **Not implemented.** There is no `@media print` block in the app. Until one exists and is re-measured, every contrast and equality figure in this document applies to the dark substrate only.

There is no print stylesheet today. For a read only tool whose output is a
decision, the artifact of a review should be a document a reviewer can staple,
initial, and file.

- `@media print` emits the surface as a light document: dark chrome prints as a black slab or inverts unpredictably.
- **Every contrast and equality guarantee in this file is measured on the dark substrate and does not transfer to white paper.** The print variant re-measures, or the guarantee is explicitly declared not to hold there.
- Evidence flattens into numbered references rather than collapsing.
- Absence states must remain visible in greyscale, which the dashed border already guarantees.

## Test Contract [TARGET]

> [TARGET] **Not implemented.** The banned-widget source scan ships. None of the property assertions below exist; the tests that do exist check notation, which is how the Color defect survived.

**Where a contract can be a construction-time raise instead of a test, make it
one.** A guard that runs when the value is built beats a guard that runs when CI
does, for three reasons a test cannot match:

- **A stub cannot satisfy it.** There is nothing to define to make it pass; the
  wrong value simply fails to exist.
- **It cannot be deleted to make the build green.** Removing a raise breaks the
  code that depends on it, which is loud. Removing a test is quiet and is what a
  red build teaches somebody to do.
- **It covers paths no test enumerates.** It fires on every construction, including
  the ones nobody thought to write a case for.

`COMPLETENESS_STATES` is the example in this repo. `scoring.py:69` and `:159` raise
on a state outside the tuple, so a `DimensionScore` carrying an unknown
completeness cannot be built at all. The contract audit measured the difference:
removing a member of that tuple failed 134 tests without a single test naming the
tuple, because the guard runs everywhere a score is constructed. The two contracts
that had nothing (`ENVELOPE_FIELDS`, the reason-code vocabulary) are both plain
data with no constructor to guard, which is exactly why they needed hand-written
pins instead.

The rest of this section is for properties with no construction site to defend:
perceptual measurements, source scans, and rendered output.

The original defect was a test asserting a representation (equal HSL strings) and
being wrong about the property (perceptual equality). Restating the same test in
OKLCH would repeat the category error one colour space over. Assert properties,
with numbers:

- Maximum pairwise L\* delta across any chip set, and maximum chroma delta.
- Minimum ΔE within any set the reader must distinguish, under normal vision plus deuteranopia, protanopia and tritanopia.
- Text contrast on every fill it can appear on, asserted as a ratio, not a hex pair.
- Boundary contrast at 3:1 for anything whose shape must be identifiable.
- Hue, if ever reintroduced, is not a monotone function of enum declaration order under any rotation.
- No banned widget appears in source (already enforced).
- No dimension receives more area than another in any rendered layout.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-08-05 | Design system created | `/design-consultation`, informed by competitive research across 7 sites, measurement of the running app, and two outside design voices |
| 2026-08-05 | Perceptual guarantees stated in OKLCH and CIELAB, never HSL | The HSL claim was false: 15.3 L\* points of spread read as an order the arithmetic denied |
| 2026-08-05 | Category hue retired in favour of one neutral chip plus form | Hue carried three taxonomies at once, collapsed to ΔE 3.4 under deuteranopia, collided with the accent at 12 degrees, and tracked enum order. The label already carried the meaning |
| 2026-08-05 | Type carries provenance: serif asserts, mono records, sans is furniture | Serves "every claim shows its work" at a glance, and makes inference impossible to mistake for record |
| 2026-08-05 | Motion formalised as none | Matches what already ships; animation implies moving data in a tool that publishes a record |
| 2026-08-05 | Sort controls refused on all five dimensions | A sort by one dimension is a ranking, which is the composite this tool refuses to compute |
| 2026-08-05 | Category hue retired in code (`282657a`) | Nine of eleven hues never reached a badge, so this was a latent trap rather than a live defect. The first caller to write `badge(row.completeness)` would have shipped an ordered ramp with three guards saying it could not rank |
| 2026-08-05 | Absence kinds named in the coverage panel (`9e3c25a`) | Three kinds shipped, four reserved. Labels exist only for distinctions the model can actually make |
| 2026-08-05 | Order label stopped promising a rank-by control (`f4130e0`) | Resolved QA ISSUE-007 under the anti-ranking contract rather than by building the control, because sorting by one dimension declares it the ranking |
