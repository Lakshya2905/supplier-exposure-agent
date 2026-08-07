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

**Substrate: light, since 2026-08-07.** Page `#F7F8FA`, panel `#FFFFFF`. Every
contrast and equality figure below is measured on it.

This document used to carry the warning that a light variant "voids every
guarantee in this document until the numbers are re-measured on that substrate".
That warning was taken at its word. **The ramp was not inverted; it was solved.**
Each step was searched for the contrast its dark counterpart held against
`#14171A`, and the light value is the first that meets or exceeds that floor:

| Step | Dark | on `#14171A` | Light | on `#F7F8FA` |
|---|---|---:|---|---:|
| `text-title` | `#F0F2F4` | 16.03:1 | `#1A1C1E` | **16.08:1** |
| `text-primary` | `#E3E6E8` | 14.35:1 | `#222527` | **14.51:1** |
| `text-body` | `#D5DADE` | 12.78:1 | `#2C2E31` | **12.81:1** |
| `text-note` | `#9BA3AA` | 7.04:1 | `#50555B` | **7.08:1** |
| `text-caption` | `#838C94` | 5.26:1 | `#61686E` | **5.32:1** |
| `text-section` | `#8FA0AD` | 6.68:1 | `#53585E` | **6.76:1** |
| `accent` | `#7FB2D9` | 7.94:1 | `#194F7D` | **8.05:1** |

**Three tests changed, and two of them had been asserting properties of the dark
palette rather than of the design.** One required the sidebar to sit *below* the
just-noticeable difference from the page, which was a finding about one set of
greys turned into a requirement; it now asserts the conditional that was always
the real rule — if two surfaces are within the JND, a rule has to separate them.
Another asserted `border-ui` was too weak to serve as a focus ring, which was
true on dark at 2.6:1 on a chip and is false on light at 4.2:1; it now asserts
what that argument was really protecting, that focus must not look like a
resting boundary. The third read a literal hex and failed while the rule was
correct, which is corrections entry 6 for the third time.

**Print still restates its own colours** rather than inheriting these. The two
substrates are closer now, but "closer" is not "the same", and the print block
that enumerates its values is the one that survived a substrate change without
being touched.

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

> [PARTIAL] Light, minimal and motionless ship today. The shift in register from monitoring console to instrument record is a target. The substrate moved from dark to light on 2026-08-07; every ratio was re-derived rather than inverted.

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
| `bg` | `#F7F8FA` | page |
| `surface` | `#FFFFFF` | bordered panel |
| `surface-head` | `#F0F2F5` | panel header strip |
| `surface-sidebar` | `#EFF1F4` | sidebar |
| `border-hairline` | `#E2E6EB` | dividers, table rules |
| `border-panel` | `#D9DEE4` | panel edge |
| `border-ui` | `#6A7178` | anything whose boundary must be identifiable (4.95:1 on surface, 4.65:1 on bg, 4.21:1 on a chip) |

### Text ramp, with the semantic mapping [SHIPPED]

> [SHIPPED] The tokens are declared once in `:root` and every text colour in the stylesheet names one. `tests/test_design_contracts.py` refuses a seventh step, and refuses a caption whose text varies with the data.

Five greys with no usage rule will be chosen by feel and drift within a week, so
the rule is part of the system. Twelve distinct text colours shipped against
these six, which is the same failure the type scale had: a list, decided one
rule at a time. Every one of the six extras folded onto a step that already
existed, which is the evidence that none of them was carrying a distinction.

| Token | Hex | On bg | Means |
|-------|-----|------:|-------|
| `text-title` | `#F0F2F4` | 16.03:1 | h1 only |
| `text-primary` | `#E3E6E8` | 14.35:1 | a finding, and any value read from a source: identifiers, figures |
| `text-body` | `#D5DADE` | 12.78:1 | prose, chip labels, absence states |
| `text-note` | `#9BA3AA` | 7.04:1 | a qualification attached to a finding |
| `text-caption` | `#838C94` | 5.26:1 | instructions about the interface, never about the data |
| `text-section` | `#8FA0AD` | 6.68:1 | a section label, at any heading level below h1 |

**Heading level is carried by size, weight and position, never by hue.** `h3`
through `h6` used to have a colour of their own, which made "how deep is this
heading" a thing the palette answered twice and the type scale answered once.

`text-note` and `text-caption` are not interchangeable. A note is about the data.
A caption is about the interface. If it would still be true with different data,
it is a caption.

**Only one direction of that is mechanisable, and it is enforced.** A caption
that interpolates a computed value is provably about the data, so it is provably
in the wrong register; the converse is a judgment about meaning and is left to
review. Five captions were carrying counts and are now notes. A caption may still
name a module-level constant: "ordered by part number" reads the same against any
dataset.

**Two steps were not reaching the screen at all.** Streamlit's theme sets
`textColor` in `config.toml` and paints headings with it at a specificity these
element rules lose to, so every heading on the page measured `text-primary` and
`text-title` and `text-section` were never painted. That was equally true when
the declarations were literals — tokenising did not cause it. **No scan of the
stylesheet could have found it**, because the stylesheet was right; the rendered
page was wrong. Found by measuring `getComputedStyle` on the running app.

### The accent contract [SHIPPED]

> [SHIPPED] Accent usage and every ratio below ship and are verified, and every accent element now carries a second, non-colour cue. `tests/test_design_contracts.py` refuses an accent rule with no affordance in the same block.

- **`accent` `#7FB2D9`**, 7.94:1 on bg, 7.48:1 on surface, 6.91:1 on panel head.
- The accent marks **only** what a reviewer can act on or navigate to: links, expander summaries, the active nav rule, button borders, and the outlined autonomy chip (which is exactly the `recommends` state, the one that gets a Confirm and Reject button).
- The accent is **never** applied to a finding, a part, a dimension, or a category.
- **Colour is never the only cue for actionability** (WCAG 1.4.1). Every actionable element also carries a non colour affordance: links and expander summaries an underline, buttons and the outlined chip a border, the selected nav item a left rule, focus an outline. The expander summary carries its own underline rather than relying on Streamlit's chevron: the chevron is a real affordance and it is there, but it is a vendor's markup and not a contract, so the only thing standing between that control and a colour-only cue would be somebody else's release note.
- **The link colour was losing, and the source said otherwise.** Streamlit styles its own anchors from a hashed emotion class, which beats an element rule, so every link rendered in Streamlit's blue — measured `rgb(61, 157, 243)` against the accent's `rgb(127, 178, 217)` — while the stylesheet and a test both said accent. The underline had been winning the whole time, because Streamlit sets no `text-decoration` there, which is what made it quiet: the affordance was right and only the colour was wrong.
- Nothing in the chip vocabulary may land near the accent's hue, `oklch(0.742 0.078 242)`. This is why the category palette does not use hue at all.

### The category chip: one neutral chip, form carries taxonomy [SHIPPED]

> [SHIPPED] Implemented in `282657a` and `9e3c25a`. Verified in a browser: every
> chip renders `#EAEDF1` with `#2C2E31` text at 12px, no inline styles, and the
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
| solid | fill `#EAEDF1`, 1px `#C7CED6`, text `#2C2E31` at **11.60:1** | an asserted category |
| outlined | transparent fill, 1px `accent`, text `accent` at **7.48:1** on surface | this row has a control (redundant with the control, see below) |
| dashed | fill `#EAEDF1`, 1px dashed `#6A7178`, text `#2C2E31` | an absence, see below |

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

**`no record` has since shipped, and what unblocked it is worth recording.** It
was reserved because the model could not tell "the source has no row for this"
apart from "nobody has looked". The extract manifest settles exactly that: a file
with a system of record and a retrieval time *was* pulled, so an absence in it is
a recorded absence. The evidence panel now says which source was pulled, when,
and that it holds no row for this part.

| Kind | Label | Means |
|------|-------|-------|
| `no_record` | `no record` | the source was retrieved on a stated date and has no row for this |

**Reserved, not implemented.** The model cannot currently distinguish these, and
an earlier draft of this document specified them as though it could. Inventing a
label for a state the data cannot tell apart is the interface claiming a precision
the model does not have, so no label exists until the model can produce the
distinction:

| State | Label when it exists | Means |
|-------|----------------------|-------|
| stale | `as of <date>` | a record exists but predates the as-of horizon |
| conflicting | `sources disagree` | two sources answer differently and neither wins |
| structurally unknowable | `cannot be established` | no source could answer this even in principle |

`sources disagree` is closer than it was: the evidence panel renders
contradictory lead time records side by side without choosing. What is missing
is the *chip*, because nothing in seed 42 produces a contradiction, and a label
whose only exercise is a unit test would be a claim about data this system has
never seen.

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

## Evidence [SHIPPED]

> [SHIPPED] The anatomy is a structured contract in `src/interface/model.py` and every field resolves to something in the data. `tests/test_evidence_anatomy.py` checks that a citation can be **followed**, not that the panel contains the right words.

The memorable thing is "every claim shows its work," so evidence is specified in
more detail than the palette.

### Anatomy [SHIPPED]

Every claim resolves to one or more evidence records, and each record carries:

1. **source id** (mono): the file and row that produced the value. Carried by the reader from the line the value came off, before the sort reorders anything.
2. **system of record**: which system the extract came out of, and whether the value is `recorded` (it appears verbatim in a file) or `derived` (this pipeline computed it).
3. **field cited**: the exact column, spelled as the source spells it. The constants come from the same module the readers use, so a rename moves both together.
4. **as of**: when the record was retrieved, from `sources.csv`.
5. **transformation applied**: any normalisation, unit conversion, or fuzzy name merge, stated with both the original and the resolved string.
6. **inverse link**: the locator, `file:row`, which the plain-text export also carries, so a raw line can be traced back to the claims that used it.

**Field 2 was called "source type" and that name was already taken.**
`source_type` is a `part_master.csv` column meaning make or buy, and it is
load-bearing in the verdict table. A panel showing "source type: buy" beside
"source type: ERP part master" puts two unrelated facts under one word, so the
anatomy was renamed rather than the column.

**Two of these six had no source until the generator grew one.** System of
record and as-of could not be answered from seed 42's data at all, and the
alternative was to render them from constants in the interface. That would have
been the panel whose entire job is proving nothing was invented inventing a
provenance at render time. `sources.csv` is the fix: the generator emits the
extract manifest and the pipeline reads it like any other input. See
`docs/DATA_DICTIONARY.md`.

**A derived value cites no line, deliberately.** A contribution figure appears in
no file, so a locator beside it would point at a row holding a different number,
and a reviewer who followed it could not tell which of the two was wrong.
`Citation.__post_init__` refuses to construct either mistake.

### Rules [PARTIAL]

> [PARTIAL] Every rule below ships except the sigil being its own target: the sigil renders and the merge is stated beside it, but there is nothing to open.

- **The evidence view shows the source as the source spells it.** Original column headers, original casing, original whitespace. No relabeling, no realignment to the pretty grid, no unit prettification. If it looked designed, a reviewer would suspect it had been processed.
- **A merge is always visible before it is asked about.** It was buried inside the expander, which put the one inference a reviewer is most likely to disagree with behind a click. The finding now carries an inline mono sigil at `text-note` — never the accent, because a reader cannot act on a merge — and the merge, with both strings, sits beside it outside the panel. **One sigil whatever the count**: repeated marks are a tally, and a tally is a magnitude drawn as punctuation.
- **The two merges are not the same claim.** A cross-file merge reconciles two spellings across two files and changes no count. A duplicate vendor merge collapses two rows of *one* file into one supplier and therefore **changes the supplier count**, which is the number the verdict turns on. A reviewer counting rows in the panel gets two where the sentence says one, so the collapse is stated rather than left to be inferred.
- **Absent evidence is a specified state, not an empty panel.** A claim with no evidence says so in the same vocabulary as the Absence section, and names the source and its retrieval date.
- **Contradictory evidence is shown, never resolved.** Both records render. The tool does not pick. The previous join was a dict comprehension keyed by canonical name, so two rows that canonicalised together silently kept the last one — a latent trap rather than a live defect, since nothing in seed 42 triggers it.
- **Never render a bare count of sources.** "3 sources" invites reading count as strength, and three weak records do not outrank one authoritative one. Show source identity and type. Never render a tally as repeated marks.
- **Evidence is exportable as plain text**, carrying file, retrieval time, row ids, and every transformation applied, so a citation can be pasted into a review memo intact.

## The Decision Panel [SHIPPED]

> [SHIPPED] Implemented in `4dbd406`, built last on purpose. Everything it would
> have exposed was fixed first: the epoch timestamp (`b898c81`), the arity a
> cluster decision dropped (`7ff6f14`), the duplicate append (`e6d1a72`), and the
> `note` shadowing that would have crashed the first attempt (`a950c00`).
> Verified in a browser at both states.

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

### Known trap, now fixed: `note` was shadowed at the panel's insertion point

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
the first instinct will be to change the panel. Fixed in `a950c00`: the widget local is
`note_text`, and a source-level guard asserts that no painter binds a local named
after a module helper, so this cannot return through a different function. Kept
here because the reasoning generalises: a name collision reports itself at the
call site, not at the binding.

## The Anti-Ranking Contract [PARTIAL]

> [PARTIAL] Dimensions stay separate, no sort control exists, the order label declares the order meaningless as of `f4130e0`, and equal area now holds and is tested. The written no-default-sort rule is still enforced by nothing.

**Equal area was being violated by the lattice itself.** Each layer sized its
columns to its own group count, so a layer holding one group filled the page and
a group sharing a layer with two others got a third of it. Nothing about a group
differed between those two states except how many siblings it happened to have,
and a reader has no way to know that: a full-width panel simply reads as the
important one. Vertical position carries dominance and is meant to; width
carried nothing and looked like it carried something, which is the objection
that retired the category hue. `lattice_width()` now returns one column count
for the whole lattice. Measured at 1440px: every group panel is 332px across
layers of three different sizes, and the coverage panel stays full width because
it is a page-level panel rather than a group.

The five scoring dimensions stay separate forever. That is a correctness
constraint, and layout can violate it as easily as arithmetic can.

- **Fixed order, declared arbitrary.** The dimensions render in one order, always, and the interface says in words that the order carries no meaning.
- **No dimension gets more area, weight, or colour than another.** Identical geometry is the encoding: the reader compares contents, not sizes.
- **No default sort derived from more than one dimension.** That is a composite score with the number hidden.
- **No sort control on any dimension.** A reviewer who sorts by dimension three has declared dimension three the ranking. Sorting is a smuggled conclusion; filtering is a stated question, so filtering is offered freely. Where a sort control would have been, say why there is none.
- **Reading order is not priority.** If a set must be laid out linearly, say so.
- **The order label stays; the promise of a control goes.** `CLAUDE.md` requires that any default ordering be arbitrary, stable, and labelled in the output, "because a plausible default is read as a ranking." `DEFAULT_ORDER_LABEL` in `src/ranking.py:40` reads "ordered by part number; choose a dimension to rank by". The first clause satisfies that rule and must stay. The second promises a control that does not exist anywhere in the app (0 sort controls, 0 sliders, 0 radios outside navigation) and that this contract says should never exist. Drop the second clause only.

### Banned widgets [RETIRED 2026-08-06]

> [RETIRED] The owner retired the nominal-only encoding rule on 2026-08-06, after being told what it costs. Charts, a choropleth and red/amber/green are permitted. The source scan that enforced this list is gone; `tests/test_scoring.py` still forbids the arithmetic composite and did not change.

The list is kept because the reasoning is still true, and because a reader who
finds a bar chart here should be able to see that it was a decision rather than
an oversight. **These are arguments that were overruled, not arguments that were
refuted.**

| Was banned | The objection, which still stands | Status |
|--------|-----|---------|
| `st.progress`, `ProgressColumn` | a literal 0 to 1 bar | permitted |
| `BarChartColumn`, `LineChartColumn`, `AreaChartColumn` | magnitude as length inside a table | permitted |
| `st.bar_chart`, `st.line_chart`, `st.area_chart`, `st.scatter_chart` | shared axis across incommensurable dimensions | permitted for ONE dimension in its own units |
| `background_gradient`, `color_gradient` | ordinal encoding of a heterogeneous set | permitted |
| `st.slider` | a threshold with no owner and no version | **still banned**: this is about threshold ownership, not encoding, and `config/archetypes.yaml` remains where a threshold lives |
| `st.metric(delta=...)` | ships red and green delta arrows | permitted |
| `st.dataframe` column sort | free per column sort supplies a ranking silently | permitted |
| red / amber / green anywhere | three stops on one ordered axis wearing a costume | permitted |

**The one line that did not move.** Nothing may put two dimensions on a single
axis. That is not the encoding rule, it is the composite rule, and it is
enforced in `src/scoring.py` at construction: a profile has no `total`, no
`weight` and no `__add__`, and every measure keeps a physical unit. A chart may
draw lead time in days; no chart may draw lead time against blast radius as
though the two commensurate.

Green is still worth thinking about before using it. No dimension here has a
"good": a part with one qualified supplier is not good, it is concentrated,
which may be fine or fatal depending on the other four.

## The Dashboard Surface [SHIPPED]

> [SHIPPED] Added 2026-08-06, when the owner retired the nominal-only encoding rule. Four figure tiles, a region choropleth, five small multiples and a supplier-to-part incidence grid.

**A fourth surface, not a merger of the other three.** Each of those has one row
entity and answers one question. This one has no row entity and answers none of
them: it is an overview, and every decision is still made elsewhere. That is why
adding it does not breach "three surfaces, never one table" — it is not a table
of parts, fields and clusters flattened together.

**It is the landing surface.** A visitor meets the shape of the set before the
findings.

What it draws, and the one line each respects:

| Element | Encoding | The care taken |
|---|---|---|
| Figure tiles | number | Every tile carries its denominator. A count with no denominator invites reading 21 as large or small when neither is knowable. No `delta`: there is no previous run, and an arrow pointing at a number that does not exist is worse than no arrow |
| Region choropleth | sequential fill | The data has four regions and no coordinates. Countries are a **drawing convention**, and the surface says so above the map, because a map is the most believable thing on a page. India is drawn from vendored geometry; see below. See also the defects below |
| Five small multiples | length | **Identical geometry, five separate axes.** Retiring the encoding rule allowed the charts; it did not make days and finished-good units the same quantity. Rows are padded to three columns so a row of two does not draw wider boxes |
| Incidence grid | presence | Binary. The shade carries nothing |

**Absence keeps its own count in every series.** A histogram built by filtering
out the unknowns is a picture of the answerable parts presented as a picture of
the parts, so each chart states how many were not established beneath it.

**The two reasons a part is missing from the incidence grid are not one fact.**
A part can be absent because the grid is capped, or because it has no supplier
row at all — and the second is the finding, the parts with nobody to call.
Reporting one count for both would bury it.

Three defects that only using the page found: the paired lead-time chart drew
two overlapping histograms with its legend switched back off by the shared
layout helper, so nothing said which was quoted and which was p95; the
choropleth captured the mouse wheel, so scrolling the page over the map zoomed
the map and the page stayed put; and the tile denominators were captions, which
the caption contract correctly rejected as data.

### India is drawn from vendored geometry [SHIPPED]

Plotly's built-in country shapes come from Natural Earth, whose `IND` polygon
follows a different convention and stops around 35.5°N. **That geometry ships
inside plotly.js and no option reaches it**, so the only way to draw India
complete is to supply the shape.

`assets/india-claimed.geojson` is India including Jammu & Kashmir, Ladakh, Aksai
Chin, the Shaksgam Valley, Pakistan-administered Kashmir and Arunachal Pradesh,
per the official boundary published by the Survey of India. Source
[datameet/maps](https://github.com/datameet/maps) under **CC BY 4.0**, simplified
by `tools/simplify_boundary.py` from 10.5MB and 252,604 coordinate pairs to 45KB
and 2,598, at a 0.02° tolerance derived from the pixel size the map is drawn at.

**It is drawn last, so it is drawn on top.** India is excluded from the ISO-3
trace and added as its own, which means the claimed areas Natural Earth assigns
to neighbours are covered by India's fill rather than left showing a border
through them. It shares the figure's colour axis, so it takes the same fill the
scale gives every other region rather than a second palette nobody declared.

`tests/test_map_geometry.py` asserts the **extent**, not the file: north of 36°N,
east of 96°E, west of 68.5°E. A resimplification that quietly clipped a claimed
region would otherwise render as a smaller India rather than as an error, and on
a map that is a different claim rather than a rendering artefact. The attribution
CC BY 4.0 requires is rendered beneath the map, not only filed in
`assets/README.md`, because a licence satisfied only in a repository is satisfied
only for people who read repositories.

### What was wrong with the first map [FIXED]

Three defects shipped in the first version, and the shape of all three is the
same: **a plotly default that is correct on a white page and wrong on this one**,
none of which raised an error.

**The rest of the world was not drawn.** `landcolor` and `countrycolor` were set
without `showland` or `showcountries`, and both default to off under a
choropleth, so nineteen filled countries floated in an empty rectangle: no
Africa, no South America, no Australia, no Russia. A map missing four continents
is not a stylistic choice. It says the world ends at the edge of the dataset.

**The map sat on a white slab.** `geo.bgcolor` defaults to `#fff` and is covered
by neither `paper_bgcolor` nor `plot_bgcolor`, so the one element on the page
with a light background was the largest one.

**Absence and a low count were the same colour.** The shared chart palette
starts at `#1E2933`, within a step of unmapped land, so the least-exposed region
and "not a supplier region at all" would have rendered alike. Those are
different claims — one is a count, the other is a question the data does not
answer — and the map is the one place they are told apart by fill alone, since
a country carries no label. The map now has a palette of its own starting at
`#3A6076`, **25.7 ΔE** from the land, and a test holds it above the
just-noticeable difference.

**Countries are cited by ISO 3166-1 alpha-3, not by name.** Every name resolved
when checked, but names resolve by string match against a vendored gazetteer, so
a country renamed upstream stops matching and its fill disappears with no error.
Czechia, Türkiye and Eswatini have all moved. A missing country reads as "no
suppliers there", which is a different claim from "this label stopped matching",
and the map cannot tell a reader which happened.

**A region absent from the mapping used to vanish silently.** `regions()`
iterated the country dict, so a supplier region the map could not draw
disappeared from the table as well. It now iterates the union and the table says
`not on the map`.

**None of this was visible to the test suite**, which passed throughout. It was
found by reading `getComputedStyle` and the plotly layout off the running page —
the same method that found the link colour and the two unpainted ramp steps.

### Charts on the three decision surfaces [SHIPPED]

Once charts were permitted, the question stopped being *whether* and became
*where*. Each one below answers a question the page was already asking; nothing
was added because a page looked empty.

| Surface | Chart | The question it answers | Its ordering |
|---|---|---|---|
| Exposure | coverage bar | which gap accounts for most of what was not assessed | by count, and it says so |
| Exposure | group sizes | how many parts sit in each archetype | **lattice order, never by size** |
| Exposure | blocking matrix | which finished goods each part can stop | binary grid, replaces the table |
| Find out | parts per field | which single trip settles the most | by count, and this one *is* a ranking |
| Confirm | cluster sizes | how much one confirmation covers | by count, **coloured by basis** |

**The orderings are the part that regresses silently**, so each is tested. Two
deserve their reasoning stated:

**Group sizes keep the lattice's order and are never sorted by count.** The
chart sits directly under a layout that says in words that these groups are
incomparable. A bar chart is a stronger cue than a caption, so sorting it by
size would overrule the thing it sits beneath.

**Cluster sizes are coloured by basis, not merged into one ranking.** Supplier
concentration and region concentration are a *complementary* disagreement: both
can be true at once, and no fact anybody could go and find settles one against
the other. A single undifferentiated bar chart would assert that a supplier
cluster of six loses to a region cluster of twenty-eight, which puts them in
exactly the relation the analysis says they are not in.

**What was not built, and why.** No per-part radar or parallel-coordinates plot
of the five dimensions. That is the one chart the retired rule and the surviving
one agree about: it puts five units on one axis, which is the composite drawn
rather than computed, and `src/scoring.py` still refuses to compute it.

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

### Fields had no boundary at all [FIXED]

Every text input and select painted a 1px border in **the same colour as its own
fill**, so there was no boundary: the only thing separating a field from its
surroundings was the fill difference, **1.04:1** in the sidebar and **1.09:1** on
the page. Both sit around a single just-noticeable difference. WCAG 1.4.11 asks
3:1 for the boundary of a UI component, and before that, a reviewer simply could
not see the box.

The worst case was the name field on Confirm, which is the one control a decision
cannot be recorded without.

**`border-ui` had been specified in the Surfaces table from the start and no form
control ever referenced it.** That is the part worth remembering: a token can be
declared, correct, and unused, and nothing about the declaration reveals it. The
fields now carry it at **3.82:1** in the sidebar, **3.69:1** on the page and
**3.40:1** against their own fill, and a test asserts both the ratio and that
the rule references the token.

Streamlit 1.61 renders these through react-aria rather than baseweb, so the
selectors are the testid it emits and the ARIA role, not an emotion class.

## Focus and Keyboard [TARGET]

> [TARGET] **Focus indicators are not implemented.** Streamlit defaults are whatever they are and have not been measured. The reviewer-name persistence bullet is the exception: that one shipped in `6d1a8ae`.

- Every interactive element has a visible focus indicator at **3:1 or better** against both the element and the surface behind it (WCAG 2.4.7, 2.4.11). `border-ui` `#6A7178` satisfies it on every surface, and the accent carries the ring itself.
- Focus is never indicated by colour alone.
- Tab order follows reading order.
- The reviewer name field must not lose its value on navigation. It sits in the sidebar but is created inside the confirm surface, so Streamlit discards its state on any surface change; hold it in a plain `session_state` slot that no widget owns.

## Print [PARTIAL]

> [PARTIAL] Implemented in `154aaba`. Print inverts to black on white and is
> its own substrate, not the dark theme with a filter over it. One part of the
> page is out of reach: `st.dataframe` renders through glide-data-grid onto a
> **canvas**, so its pixels are painted from JavaScript and no CSS rule can
> recolour them. It prints in the screen palette as a self-contained dark
> block. Verified by rendering to PDF: 13 fills survive every override, at
> `#E3E6E8`, `#C9D2D9` and `#838C94`, all inside the grid.
>
> Left visible rather than hidden, because it draws its own background and is
> legible on paper, and hiding it would silently drop the blocking matrix from
> the record.

There is no print stylesheet today. For a read only tool whose output is a
decision, the artifact of a review should be a document a reviewer can staple,
initial, and file.

- `@media print` emits the surface as a light document: dark chrome prints as a black slab or inverts unpredictably.
- **Every contrast and equality guarantee in this file is measured on the light substrate and still does not transfer to white paper.** Closer is not the same: paper has no `#F7F8FA` and no panel fill. The print variant re-measures, or the guarantee is explicitly declared not to hold there.
- Evidence flattens into numbered references rather than collapsing.
- Absence states must remain visible in greyscale, which the dashed border already guarantees.

## Test Contract [SHIPPED]

> [SHIPPED] `tests/test_design_properties.py`. Nothing there compares a hex
> pair: every assertion computes a ratio or a CIELAB distance from the colours
> the stylesheet declares and fails on the number. Verified by regression:
> dropping the chip label to the border token fails the legibility assertion.

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
| 2026-08-06 | Provenance emitted by the generator, not assembled in the interface | Two of the six anatomy fields had no source in the data. Rendering them from constants would have made the panel that proves nothing was invented invent a provenance at render time |
| 2026-08-06 | Anatomy field 2 renamed from "source type" to "system of record" | `source_type` is a `part_master.csv` column meaning make or buy and is load-bearing in the verdict table. One word cannot carry both, and the CSV name is the older one |
| 2026-08-06 | `no record` promoted from reserved to shipped | The extract manifest is what made the distinction available: a file with a retrieval time was pulled, so an absence in it is recorded rather than unexamined |
| 2026-08-06 | Findings moved out of the layer loop into one list (QA ISSUE-005) | 36 findings for 21 parts, 14 of them verbatim duplicates. Rendering each part under its first group would have deduplicated equally and made placement depend on iteration order, which reads as a ranking |
| 2026-08-06 | Text ramp declared once in `:root`, twelve colours folded to six | Every extra folded onto a step that already existed, which is the evidence none was carrying a distinction. The caption rule is enforced in the direction that is mechanisable |
| 2026-08-06 | Heading and link colours given `!important` | Both were losing to Streamlit's own rules while the stylesheet and its tests agreed they were right. Two of the six ramp steps were never painted. Only measuring the rendered page could have found it |
| 2026-08-06 | One column count for the whole dominance lattice | A group's width varied with how many siblings its layer held, so a solo group filled the page and read as the important one. Width carried nothing and looked like it carried something |
| 2026-08-06 | **Nominal-only encoding rule retired, by the owner, on the record** | Asked for a dashboard with charts and a world map; told what it costs before deciding. The objection was overruled, not refuted: an ordinal encoding across incommensurable dimensions is a composite a reader assembles by eye. A greyscale screenshot no longer recovers everything the screen carries |
| 2026-08-06 | The arithmetic composite rule kept, explicitly | Separate from the encoding rule and about what the agent computes rather than how it looks. No total, no weight, no `__add__`, every stored measure keeps its unit, and `tests/test_scoring.py` is unchanged |
| 2026-08-06 | Dashboard added as a fourth surface, and as the landing page | It has no row entity and decides nothing, so it does not flatten the three decision surfaces into one table |
| 2026-08-07 | Charts added to the three decision surfaces, each answering a question the page already asked | Nothing was added because a page looked empty. The orderings are tested, because a bar sorted the wrong way asserts a ranking in the one place this product refuses to compute one |
| 2026-08-07 | Group sizes drawn in lattice order, never by count | The chart sits under a layout that says these groups are incomparable, and a bar chart is a stronger cue than a caption |
| 2026-08-07 | Cluster sizes coloured by grouping basis rather than merged | Supplier and region concentration are a complementary disagreement. One ranking would assert that a supplier cluster of six loses to a region cluster of twenty-eight |
| 2026-08-07 | No radar or parallel-coordinates plot of the five dimensions | The one chart the retired encoding rule and the surviving composite rule agree about: five units on one axis is the composite drawn rather than computed |
| 2026-08-07 | World map fixed: whole world drawn, white slab removed, ISO-3 codes | Three plotly defaults that are right on a white page and wrong on this one, none of which raised an error. The suite passed throughout |
| 2026-08-07 | The map got a palette of its own, floor 25.7 ΔE from unmapped land | Absence and the lowest count are different claims, and the map is the one place they are separated by fill alone because a country carries no label |
| 2026-08-07 | Form fields given the `border-ui` boundary they were always specified to have | Every field drew a border in its own fill colour, so the name box on Confirm was invisible at 1.04:1. The token was declared and correct and had never been referenced by anything |
| 2026-08-07 | **Substrate changed from dark to light** | Owner's call. Every ratio re-derived against the floor its dark counterpart held, never inverted by eye, because this document said a substrate change voids its own guarantees until they are measured again |
| 2026-08-07 | Two colour tests restated: they were pinning the dark palette, not the design | One required the sidebar to sit below the JND from the page; one required `border-ui` to be too weak for a focus ring. Both were findings about one set of greys, and both failed on a correct design |
| 2026-08-07 | India drawn from vendored geometry including its full claimed territory | Plotly's built-in `IND` follows Natural Earth and stops near 35.5°N, and that shape ships inside plotly.js where no option reaches it. The claimed boundary is drawn on top, so areas Natural Earth assigns to neighbours are covered rather than split by a line |
