"""Streamlit review interface. It paints the view model and decides nothing.

THREE SURFACES, NEVER ONE TABLE. Each answers a different question for a
different person at a different moment, and each has a different row entity: a
part, a field, a cluster. A unified view has to pick one, and the other two get
denormalised. That is not a preference; flattening clusters to parts would make
a reviewer confirm one judgment once per member and would empty `member_count`
of meaning.

WIDGETS THAT ENCODE MAGNITUDE WERE BANNED UNTIL 2026-08-06, when the owner
retired the encoding rule deliberately and with the cost stated. Charts, a
choropleth and red/amber/green are permitted, and the Dashboard surface uses
them. CLAUDE.md and DESIGN.md carry the decision; this file does not re-argue it.

THE ARITHMETIC RULE DID NOT MOVE, and it is the one that made the encoding rule
worth having. No chart here puts two dimensions on one axis, because days and
finished-good units are not the same quantity and no picture makes them one.
`src/scoring.py` still refuses a total, a weight and an `__add__`, and
`tests/test_scoring.py` still checks it.

AUTONOMY IS AN AFFORDANCE. Rows that execute get no button. That is checked in
the model, which refuses to construct such a row, and again here.
"""
from datetime import datetime, timezone

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import governance as gov
from src.governance import render as govrender
from src import ranking
from src.interface import actions
from src.interface import dashboard as dash
from src.interface import model as view
from src.pipeline import default_data_dir, run, surfaces
from src.synthetic.model import (ANNUAL_UNITS, QUOTED_LEAD_TIME_DAYS,
                                 SUPPLIER_NAME)

st.set_page_config(page_title="Supplier exposure review", layout="wide")

# An operational console: SAP, an MRP screen, a procurement terminal. Dense
# rows, aligned columns, monospace identifiers, high information per screen.
# Bordered panels and surface fills carry structure; badges carry category.
#
# THE CHIP VOCABULARY IS STILL NOMINAL, and that is now a choice rather than a
# rule. Every badge is one colour and one weight: a set where one chip is red and
# another green has an order, and the three decision surfaces are where a reader
# is deciding, so nothing there should suggest an order the arithmetic will not
# defend. The Dashboard surface, added when the encoding rule was retired, uses
# colour and length freely. The accent still appears only on what can be acted
# on, and every accent element still carries a second, non-colour cue.
CONSOLE_CSS = """
<style>
  /* THE TYPE SCALE, DECLARED ONCE. Ten sizes shipped before this, with step
     ratios from 1.012 to 1.426, which is a list rather than a scale. Five steps
     in two zones, stated honestly: a dense console needs finer steps in its UI
     range than a modular ratio would give, so the UI zone is 12/13/14 and the
     document zone is the reading size and the title.

     Sizes live here and nowhere else. A literal font-size in a rule below is a
     sixth step nobody declared, and a test asserts there are none. */
  :root {
      --ui-xs: 0.75rem;     /* 12px  chip labels, captions. The floor. */
      --ui-sm: 0.8125rem;   /* 13px  notes, table cells, identifiers, controls */
      --ui-base: 0.875rem;  /* 14px  section headings */
      --doc: 0.9375rem;     /* 15px  finding sentences, the reading size */
      --title: 1.3125rem;   /* 21px  one per surface */

      /* THE SPACING SCALE, on a 4px base. Thirty-eight distinct rem values
         shipped before this and five of them landed on any grid, which means
         the rhythm was decided thirty-eight times. Same rule as the type scale:
         declared here, and a test asserts no rule invents a value. Optical
         adjustments that are not spacing (negative pull on a panel head, a
         baseline nudge, a min-width) keep their literals and are named below. */
      --space-xs: 0.25rem;  /*  4px */
      --space-sm: 0.5rem;   /*  8px */
      --space-md: 0.75rem;  /* 12px */
      --space-lg: 1rem;     /* 16px */
      --space-xl: 1.5rem;   /* 24px */
      --space-2xl: 2rem;    /* 32px */
      --space-3xl: 3rem;    /* 48px */

      /* THE TEXT RAMP, AND WHAT EACH STEP MEANS. Six tokens shipped in
         DESIGN.md and twelve distinct text colours shipped in this file, which
         is the same failure as the ten font sizes: a list, chosen by feel, one
         rule at a time. The six off-ramp greys are gone and every one of them
         mapped onto a step that already existed, which is the evidence that
         none of them was carrying a distinction.

         The mapping is the part that matters. Five greys with no usage rule
         will drift within a week, so the rule is part of the system and a test
         asserts no rule below invents a seventh. */
      --text-title: #F0F2F4;    /* 16.03:1  h1 only */
      --text-primary: #E3E6E8;  /* 14.35:1  a finding, and any value read from
                                             a source: identifiers, figures */
      --text-body: #D5DADE;     /* 12.78:1  prose, chip labels, absence states */
      --text-note: #9BA3AA;     /*  7.04:1  a qualification attached to a finding */
      --text-caption: #838C94;  /*  5.26:1  instructions about the interface,
                                             never about the data */
      --text-section: #8FA0AD;  /*  6.68:1  a section label, at any heading level
                                             below h1. Level is carried by size,
                                             weight and position, never by hue */
      --accent: #7FB2D9;        /*  7.94:1  ONLY what a reviewer can act on */
      /* The print substrate, declared here so no rule anywhere states a text
         colour as a literal. See the print block for why it is not a filter. */
      --text-print: #000000;
  }
  /* Middle density. The earlier revision read as an essay and the one after it
     read as congested; this sits between them. Where a region felt crowded the
     fix was usually less on screen at once rather than more air, so the panels
     carry the map and the sentences below carry the reading. */
  .block-container {
      max-width: 100%;
      padding: var(--space-xl) var(--space-2xl) var(--space-3xl) var(--space-2xl);
  }
  html, body, [class*="css"] { -webkit-font-smoothing: antialiased; }

  h1 {
      font-size: var(--title) !important; font-weight: 600 !important;
      letter-spacing: -0.01em;
      margin: var(--space-sm) 0 var(--space-md) 0 !important;
      padding: 0 !important; color: var(--text-title) !important;
      line-height: 1.35;
  }
  h2 {
      font-size: var(--ui-base) !important; font-weight: 600 !important;
      text-transform: uppercase; letter-spacing: 0.08em;
      color: var(--text-section) !important;
      margin: var(--space-xl) 0 var(--space-sm) 0 !important; padding: 0 !important;
      line-height: 1.45;
  }
  /* THE HEADING COLOURS NEEDED !important AND NOBODY HAD NOTICED. Streamlit's
     theme sets textColor in config.toml and paints headings with it at a
     specificity these element rules lose to, so h1 and every h2 through h6
     rendered at the theme colour. Two of the six ramp steps, title and section,
     never reached the screen at all: measured, every heading on the page was
     rgb(227, 230, 232), which is text-primary.

     This was true before the ramp existed, when the same declarations were
     literals. Tokenising did not cause it; measuring the rendered page is what
     found it, and no scan of this file could have. */
  h3, h4, h5, h6 {
      font-size: var(--ui-base) !important; font-weight: 600 !important;
      color: var(--text-section) !important;
      margin: var(--space-lg) 0 var(--space-xs) 0 !important; padding: 0 !important;
      line-height: 1.45;
  }
  hr, [data-testid="stDivider"] hr {
      border: none; border-top: 1px solid #2C3237;
      margin: var(--space-xl) 0 var(--space-lg) 0;
  }
  [data-testid="stVerticalBlock"] { gap: var(--space-md); }
  p, li { line-height: 1.5; color: var(--text-body); }

  p.finding {
      font-size: var(--doc); line-height: 1.58; max-width: 104ch;
      margin: var(--space-md) 0 var(--space-xs) 0; color: var(--text-primary);
  }
  p.note {
      font-size: var(--ui-sm); line-height: 1.5; max-width: 104ch;
      color: var(--text-note); margin: 0 0 var(--space-sm) 0;
  }
  .stCaption, [data-testid="stCaptionContainer"] p {
      font-size: var(--ui-xs) !important; color: var(--text-caption) !important;
      line-height: 1.5; max-width: 104ch;
      margin-bottom: var(--space-sm) !important;
  }
  /* COLOUR IS NEVER THE ONLY CUE FOR ACTIONABILITY (WCAG 1.4.1). Every accent
     element carries a second, non-colour affordance, so a reader with any form
     of colour vision deficiency, a greyscale screenshot, or the print
     stylesheet still knows what can be acted on. Links and expander summaries
     get an underline; buttons and the outlined chip already carry a border; the
     selected nav item carries a left rule; focus carries an outline.

     A test asserts the pairing rather than trusting it: any rule that sets
     `color: var(--accent)` must set an affordance in the same block. */
  /* `!important` because the bare declaration LOST, and losing is invisible in
     a source scan. Streamlit styles its own anchors from a hashed emotion class,
     which is class specificity against this rule's element specificity, so every
     link on the page rendered in Streamlit's blue while the stylesheet said
     accent and a test agreed with the stylesheet. Measured in the browser at
     rgb(61, 157, 243) rather than the accent's rgb(127, 178, 217).

     The underline had been winning the whole time, because Streamlit sets no
     text-decoration there. That is what made the defect quiet: the affordance
     was right and only the colour was wrong. */
  a, a:visited {
      color: var(--accent) !important;
      text-decoration: underline; text-underline-offset: 0.15em;
      text-decoration-thickness: 1px;
  }

  code, .identifier, .ids span {
      font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas,
                   monospace;
      font-size: var(--ui-sm); background: transparent !important;
      color: var(--text-primary) !important; padding: 0 !important;
  }
  /* THE MERGE SIGIL. A data qualification, so it takes note weight and NOT the
     accent: the accent means "you can act on this", and a reader cannot act on
     a merge. One mark whatever the number of merges, because repeated marks are
     a tally, and a tally is a magnitude drawn as punctuation. */
  .sigil {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      color: var(--text-note);
  }
  .ids {
      display: flex; flex-wrap: wrap; gap: var(--space-xs) var(--space-lg);
      margin: var(--space-xs) 0 0 0;
  }
  .ids span { display: inline-block; min-width: 6.6rem; line-height: 1.75; }

  table.tight { border-collapse: collapse; width: 100%; }
  table.tight td {
      border-top: 1px solid #262B30;
      padding: var(--space-xs) var(--space-md) var(--space-xs) 0;
      font-size: var(--ui-sm); line-height: 1.5; color: var(--text-body); vertical-align: top;
  }
  table.tight tr:first-child td { border-top: none; }
  table.tight td.num {
      text-align: right; width: 4rem; font-variant-numeric: tabular-nums;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      color: var(--text-primary); white-space: nowrap;
  }

  [data-testid="stExpander"],
  [data-testid="stExpander"] details,
  [data-testid="stExpanderDetails"] {
      border: none !important; border-radius: 0 !important;
      box-shadow: none !important; background: transparent !important;
  }
  [data-testid="stExpander"] { margin: 0 0 var(--space-md) 0; }
  /* The summary carries an underline of its own rather than relying on
     Streamlit's chevron. The chevron is a real affordance and it is there, but
     it is Streamlit's element and not a contract, so the one thing standing
     between this control and a colour-only cue would be a vendor's markup. */
  [data-testid="stExpander"] summary {
      font-size: var(--ui-sm) !important; color: var(--accent) !important;
      padding: 0 !important; width: max-content;
      text-decoration: underline; text-underline-offset: 0.15em;
      text-decoration-thickness: 1px;
  }
  [data-testid="stExpander"] summary p { font-size: var(--ui-sm) !important; }
  [data-testid="stExpanderDetails"] {
      border-left: 1px solid #2C3237 !important;
      padding: var(--space-sm) 0 var(--space-xs) var(--space-lg) !important;
      margin-top: var(--space-sm);
  }

  [data-testid="stDataFrame"], [data-testid="stTable"] {
      border-radius: 2px !important; box-shadow: none !important;
  }
  [data-testid="stDataFrame"] [role="gridcell"],
  [data-testid="stDataFrame"] [role="columnheader"] {
      font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas,
                   monospace !important;
      font-size: var(--ui-sm) !important; font-variant-numeric: tabular-nums;
  }

  .stButton > button {
      border-radius: 3px; border: 1px solid #3E5C74; background: #1E2933;
      color: var(--accent); font-size: var(--ui-sm); font-weight: 500;
      padding: var(--space-xs) var(--space-md); box-shadow: none;
  }
  .stButton > button:hover {
      background: #2A3B49; color: var(--accent); border-color: #7FB2D9;
  }

  section[data-testid="stSidebar"] {
      background: #101315; border-right: 1px solid #262B30;
      width: 16rem !important;
  }
  section[data-testid="stSidebar"] .block-container {
      padding: var(--space-xl) var(--space-lg);
  }
  section[data-testid="stSidebar"] [role="radiogroup"] { gap: 0 !important; }
  section[data-testid="stSidebar"] [role="radiogroup"] > label {
      padding: var(--space-sm) 0 var(--space-sm) var(--space-md); margin: 0;
      border-left: 2px solid transparent;
  }
  section[data-testid="stSidebar"] [role="radiogroup"] > label:has(input:checked) {
      border-left-color: #7FB2D9; background: #171C21;
  }
  /* The radio control stays visible. An earlier revision hid it by position
     and hid the label text instead, because Streamlit's internal element order
     is not a contract. The left rule and the surface fill carry the selected
     state; the control is left alone. */
  section[data-testid="stSidebar"] [role="radiogroup"] > label > div:first-child {
      transform: scale(0.8); opacity: 0.75;
  }
  section[data-testid="stSidebar"] [role="radiogroup"] p {
      font-size: var(--ui-sm) !important; line-height: 1.45; color: var(--text-caption);
  }
  section[data-testid="stSidebar"] [role="radiogroup"] strong {
      color: var(--text-body); font-weight: 600;
  }

  /* ------------------------------------------------- panels and badges --
     Surfaces and borders carry structure: where one group ends and the next
     begins. THE CHIP CARRIES NO HUE AT ALL.

     A previous revision drew each category at one HSL saturation and lightness
     and called that a nominal palette. HSL lightness is not perceptual
     lightness, so the claim was false: in CIELAB the six completeness entries
     spanned 15.3 L* points and sorted into a brightness ramp in declaration
     order. The label already named the category, and CLAUDE.md requires that
     stripping every colour lose no information, so the hue was carrying nothing
     while looking like an encoding. One neutral chip; form carries the rest. */
  /* 12px is the floor. The previous 0.68rem (10.9px) uppercase monospace with
     0.05em tracking applied the slowest reading mode, letter by letter with no
     word shape, to the densest label in the interface, and a long category name
     would have truncated. A truncated epistemic state is a wrong claim rather
     than a cosmetic problem, so the chip wraps instead. */
  .badge {
      display: inline-block; font-size: var(--ui-xs); font-weight: 500;
      letter-spacing: 0.02em; padding: var(--space-xs) var(--space-sm);
      border-radius: 3px;
      background: #242A30; color: var(--text-body); border: 1px solid #333B42;
      margin-right: var(--space-xs); vertical-align: 0.06rem;
  }
  .badge.open {
      background: transparent; color: var(--accent); border-color: #3E5C74;
  }
  /* Absence is the same footprint and the same text weight as presence. The
     dashed rule is the only difference, and it is a form cue, so it survives
     greyscale and print where a colour cue would not. */
  .badge.absent { border-style: dashed; border-color: #6B7278; }
  /* THE PANEL, SELECTED BY THE MARKER WE EMIT OURSELVES.
     These rules previously targeted [data-testid="stVerticalBlockBorderWrapper"],
     which does not exist in Streamlit 1.61: the bordered container is a
     stVerticalBlock, distinguished only by a hashed emotion class that is not a
     contract. So the rules were dead, and the panel took Streamlit's defaults,
     including an 8px radius that this design system says it does not use.

     `:has()` on our own `.panelhead` is the one stable hook available, and this
     file already depends on `:has()` for the sidebar's selected state. */
  [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .panelhead) {
      border: 1px solid #272D33 !important;
      border-radius: 4px !important;
      background: #191D21 !important;
      padding: var(--space-md) !important;
  }
  /* The head bleeds to the panel edge, so its negative pull must cancel the
     wrapper's padding EXACTLY. Both now read the same variable, so changing the
     panel padding cannot leave the head inset by a few pixels. */
  .panelhead {
      display: flex; align-items: baseline; gap: var(--space-sm); flex-wrap: wrap;
      border-bottom: 1px solid #272D33;
      margin: calc(var(--space-md) * -1) calc(var(--space-md) * -1)
              var(--space-md) calc(var(--space-md) * -1);
      padding: var(--space-sm) var(--space-md); background: #1E242A;
      border-radius: 4px 4px 0 0;
  }
  .panelhead .title { font-size: var(--ui-base); font-weight: 600; color: var(--text-primary); }

  [data-testid="stMetric"], [data-testid="stAlert"] {
      border-radius: 3px !important; box-shadow: none !important;
  }

  /* ------------------------------------------------------------- focus --
     WCAG 2.4.7 wants a visible focus indicator and 2.4.11 wants it at 3:1
     against BOTH the element and the surface behind it. The accent clears that
     on every surface in this interface by a wide margin: 6.40:1 on a chip,
     6.53:1 on a button, 7.48:1 on a panel, 7.94:1 on the page, 8.23:1 in the
     sidebar.

     THE ACCENT IS THE RIGHT COLOUR HERE, not an exception to its contract. The
     contract reserves it for what a reviewer can act on, and focus only ever
     lands on something actionable, so the ring says exactly what the accent
     always says.

     A 2px ring with a 2px offset rather than a background change: a fill would
     compete with the filled-versus-outlined distinction the chips already use,
     and offsetting keeps the ring clear of the element's own border. */
  :is(button, a, input, select, textarea, summary, [role="radio"],
      [role="combobox"], [role="option"], [tabindex]):focus-visible {
      outline: 2px solid #7FB2D9 !important;
      outline-offset: 2px !important;
      border-radius: 2px;
  }
  /* Streamlit paints its own focus treatment on several controls. Ours replaces
     it rather than sitting beside it, so a control cannot end up with two rings
     saying the same thing in different colours. */
  :is(button, input, select, textarea):focus {
      box-shadow: none !important;
  }

  /* ------------------------------------------------------------- print --
     A read-only tool whose output is a decision should produce something a
     reviewer can staple, initial and file.

     THE SUBSTRATE INVERTS, SO THE GUARANTEES DO NOT TRANSFER. Every contrast
     figure in DESIGN.md is measured on the dark surface and none of them hold on
     white paper, so this is not the dark stylesheet with a filter over it: the
     text goes to black on white and is re-measured there. Printing the dark
     theme directly would emit a black slab, or invert unpredictably per browser.

     Absence keeps its dashed rule, which is why absence was given a FORM cue
     rather than a colour one: it is the only part of the chip vocabulary that
     survives a substrate change unaltered.

     Controls do not print. A button on paper is an instruction nobody can
     follow, and the panel is a record rather than a form. */
  @media print {
      :root { --doc: 10.5pt; --ui-sm: 9.5pt; --ui-xs: 8.5pt; --ui-base: 10pt;
              --title: 15pt; }
      html, body, .block-container, [data-testid="stMain"] {
          background: #FFFFFF !important; color: var(--text-print) !important;
      }
      /* EVERYTHING, not a list of selectors. The first version of this block
         enumerated the elements to blacken, which is a whitelist: anything not
         named kept its dark-theme colour and printed as light grey on white.
         Rendering it to PDF found 5 such fills at #E3E6E8 and 36 at the accent,
         all of them effectively invisible on paper. A list of what to fix can
         only ever be as complete as the person writing it. */
      /* `:root *` rather than `*`. The screen rules set colour with !important
         at class specificity (`.identifier`, `.stCaption`), and a bare `*` is
         specificity zero, so it loses to them even with !important of its own.
         `:root *` matches their specificity and comes later in the cascade, so
         it wins. Rendering to PDF is what showed this: the first version left 13
         fills at #E3E6E8, #C9D2D9 and #838C94, all invisible on white. */
      :root *, :root *::before, :root *::after {
          color: var(--text-print) !important;
          background-color: transparent !important;
          box-shadow: none !important;
      }
      /* Links keep their identity through form, since colour is gone. */
      a, a:visited { text-decoration: underline !important; }

      /* The record, not the machinery. */
      section[data-testid="stSidebar"],
      .stButton, [data-testid="stTextInput"], [data-testid="stSelectbox"],
      [data-testid="stAlert"], [data-testid="stToolbar"] { display: none !important; }

      /* Structure survives as rules on paper, where a surface fill would print
         as a grey wash and cost more legibility than it buys. */
      [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .panelhead) {
          border: 1pt solid #000000 !important; background: transparent !important;
          break-inside: avoid;
      }
      .panelhead { background: transparent !important;
                   border-bottom: 1pt solid #000000 !important; }
      .badge { border: 1pt solid #000000 !important; background: transparent !important;
               color: var(--text-print) !important; }
      .badge.absent { border-style: dashed !important; }

      /* Evidence is the point of the document, so it prints open rather than
         collapsed. A folded disclosure on paper is a claim with its working
         removed. */
      [data-testid="stExpanderDetails"] { display: block !important;
                                          border-left: 1pt solid #000000 !important; }
      p.finding, table.tight tr { break-inside: avoid; }

      /* THE DATAFRAME IS A CANVAS AND CSS CANNOT REACH IT. Streamlit renders
         st.dataframe through glide-data-grid, which paints pixels from
         JavaScript, so the rules above stop at its edge: it prints in the screen
         palette as a self-contained dark block. Verified by rendering to PDF,
         where 13 fills survive every override above, at #E3E6E8, #C9D2D9 and
         #838C94.

         Left visible rather than hidden. It draws its own background, so it is
         legible on paper even though it does not match the page, and hiding it
         would silently drop the blocking matrix from the record. An absence a
         reader cannot see is the thing this system refuses hardest. The limit is
         stated in DESIGN.md's Print section instead of being papered over. */
  }
</style>
"""
st.markdown(CONSOLE_CSS, unsafe_allow_html=True)


def identifier(text):
    return f"<span class='identifier'>{text}</span>"


def identifier_block(items):
    """A wrapping grid of identifiers. Fourteen parts take three lines."""
    cells = "".join(f"<span>{item}</span>" for item in items)
    return f"<div class='ids'>{cells}</div>"


def badge(text, open_style=False, absent=False):
    """A neutral chip. The label carries the category; nothing ranks it.

    Three variants, and each distinction is form rather than hue, so it survives
    greyscale, colour vision deficiency, a screenshot pasted into a review memo,
    and print:

    solid    an asserted category
    open     this row carries a control. REDUNDANT with the control itself, which
             is the real affordance: CLAUDE.md requires that autonomy never be
             an appearance, because a styling distinction is one commit from
             evaporating. If the chip and the control ever disagree, the control
             is right.
    absent   something is not established. Never dimmed, because dimming an
             unknown says it matters less, which is the claim this tool exists to
             refuse.
    """
    variant = " open" if open_style else (" absent" if absent else "")
    return f"<span class='badge{variant}'>{text}</span>"


def panel_head(title, badges=()):
    chips = "".join(badges)
    return (f"<div class='panelhead'><span class='title'>{title}</span>"
            f"{chips}</div>")


def tight_table(pairs):
    """Count on the right, its sentence beside it. Aligned, one glance."""
    body = "".join(
        f"<tr><td class='num'>{count}</td><td>{text}</td></tr>"
        for count, text in pairs)
    return f"<table class='tight'>{body}</table>"


def finding(sentence):
    """The rendered sentence, given the prominence of the primary content.

    Emitted verbatim, never reassembled: the goldens pin this wording and any
    edit here would fork it from them.
    """
    st.markdown(f"<p class='finding'>{sentence}</p>", unsafe_allow_html=True)


def note(text):
    st.markdown(f"<p class='note'>{text}</p>", unsafe_allow_html=True)


@st.cache_resource
def load():
    result = run(data_dir=default_data_dir())
    return result, surfaces(result)


MERGE_SIGIL = "‡"


def merge_marker(evidence):
    """The sigil, and the merge stated BEFORE anybody opens anything.

    DESIGN.md: "A fuzzy merge is always visible before it is asked about." It
    was buried inside the expander, which means the one inference a reviewer is
    most likely to disagree with was the one they had to go looking for.

    ONE SIGIL, WHATEVER THE COUNT. Repeating it per merge would be a tally drawn
    as marks, which is a magnitude encoding wearing punctuation.
    """
    if not evidence or not evidence.transformations:
        return ""
    return f" <span class='sigil'>{MERGE_SIGIL}</span>"


def render_merges(evidence):
    """The merge lines, outside the expander, at note weight.

    A merge is a fact about the data, so it is a note rather than a caption.
    """
    for transformation in evidence.transformations:
        note(f"{MERGE_SIGIL} {transformation.rule}: "
             f"{identifier(transformation.original)} &rarr; "
             f"{identifier(transformation.resolved)}.")


def citation_column(citations, field):
    """The locator for one field, or the empty string.

    Rendered as `file:row` because that is what a reviewer opens, and it is
    what the plain-text export carries, which is what makes the chain walkable
    from a raw line back to the claims that used it.
    """
    for citation in citations:
        if citation.field == field:
            return citation.locator
    return ""


def render_evidence(row):
    """Read-only workings, one click away. There is no control in here.

    A conclusion a reviewer cannot check is a conclusion they have to trust, and
    trust is what this system replaces with verification.
    """
    evidence = row.evidence
    with st.expander("How this was worked out"):
        st.caption("Read only. Nothing on this panel changes any value.")

        # IDENTITY AND TYPE, NEVER A TALLY. DESIGN.md forbids a bare count of
        # sources: "3 sources" invites reading count as strength, and three
        # weak records do not outrank one authoritative one. So each line names
        # the file, the system it came out of, when it was pulled, and exactly
        # which rows were read.
        st.markdown("###### Sources read, and when they were pulled")
        st.markdown(tight_table([
            ("", f"{identifier(entry['source_file'])} &mdash; "
                 f"{entry['system_of_record']}, retrieved "
                 f"{entry['retrieved_at']}, "
                 f"row{'s' if len(entry['rows']) > 1 else ''} "
                 f"{', '.join(str(r) for r in entry['rows'])}")
            for entry in evidence.sources_used()]), unsafe_allow_html=True)

        st.markdown("###### Supplier rows read for this part")
        if evidence.supplier_rows:
            st.dataframe(
                [{"supplier as spelled in suppliers.csv": r.supplier_name,
                  "region": r.region,
                  "lead time on file": "yes" if r.has_lead_time else "no",
                  "quoted days": r.quoted_lead_time_days,
                  "p95 days": r.p95_lead_time_days,
                  "source": citation_column(r.citations, SUPPLIER_NAME)}
                 for r in evidence.supplier_rows],
                hide_index=True, width="stretch",
                column_config={
                    "quoted days": st.column_config.NumberColumn(format="%d"),
                    "p95 days": st.column_config.NumberColumn(format="%d")})
        else:
            note("No supplier rows exist for this part.")

        st.markdown("###### Finished goods and quantities behind the usage figure")
        st.dataframe(
            [{"finished good": r.finished_good,
              "qty per finished good": r.qty_per_finished_good,
              "annual units": ("absent from the demand plan"
                               if r.annual_units is None else r.annual_units),
              "contribution": r.contribution or "not counted",
              "source": citation_column(r.citations, ANNUAL_UNITS)}
             for r in evidence.demand_rows],
            hide_index=True, width="stretch")
        st.caption("A contribution appears in no file. It is this pipeline's "
                   "arithmetic on the two figures beside it, so it cites no "
                   "row: a locator pointing at a line that does not hold the "
                   "number is worse than none.")

        st.markdown("###### Lead time record used")
        used = evidence.lead_time_used
        if used:
            note(f"{identifier(used.supplier_name)}, "
                 f"{used.quoted_lead_time_days} days quoted, "
                 f"{used.p95_lead_time_days} at p95, from "
                 f"{identifier(citation_column(evidence.lead_time_citations, QUOTED_LEAD_TIME_DAYS))}.")
        else:
            note("None. No supplier on this part has a lead time record.")

        if evidence.transformations:
            st.markdown("###### Transformations applied")
            # BOTH STRINGS, ALWAYS. The point of showing a transformation is
            # that a reviewer can disagree with it, and nobody can disagree
            # with a result whose input has been discarded.
            st.markdown(tight_table([
                ("", f"{identifier(t.original)} &rarr; "
                     f"{identifier(t.resolved)}<br>{t.rule}")
                for t in evidence.transformations]), unsafe_allow_html=True)

        if evidence.contradictions:
            # SHOWN, NEVER RESOLVED. The tool does not pick, because picking
            # would settle a question it has no basis to settle, silently.
            st.markdown("###### Sources that disagree")
            for contradiction in evidence.contradictions:
                note(f"{identifier(contradiction.subject)}: "
                     f"{contradiction.field} is given as " +
                     ", ".join(f"{c.value} at {identifier(c.locator)}"
                               for c in contradiction.citations) +
                     ". Both are shown. This tool does not choose between them.")

        if evidence.absences:
            # ABSENCE IS NOT AN EMPTY PANEL. Same chip vocabulary, same weight
            # and footprint as an asserted value, because dimming an unknown
            # says it matters less.
            st.markdown("###### What the sources do not contain")
            st.markdown(tight_table([
                ("", absence_chip(kind) + sentence)
                for kind, sentence in evidence.absences]),
                unsafe_allow_html=True)

        for line in evidence.notes:
            note(line)

        st.markdown("###### This record as plain text")
        st.caption("Carries the file, the retrieval time, every row id and "
                   "every transformation, so a citation pastes into a review "
                   "memo intact and a raw line can be traced back to the "
                   "claims that used it.")
        st.code(evidence.as_text(), language=None)

        st.caption(
            "To change any value above, correct it in the system of record and "
            "re-run. This interface never writes to source data.")


# WHICH KIND OF NOT-ASSESSED. The kinds are not interchangeable and a reader who
# cannot tell them apart will collapse them into one shrug. An unresolved supplier
# list is a fact about the data; a question that does not attach is a fact about
# the part; a threshold nobody has set is a deliberate decision somebody owns. The
# sentence says which, but only in prose, and prose does not survive skimming.
#
# Only the three kinds the pipeline actually produces are listed. Inventing labels
# for states the data cannot yet distinguish would be the interface claiming a
# precision the model does not have.
ABSENCE_LABEL = {
    "unplaceable": "unresolved",
    "not_applicable": "not applicable",
    "no_thresholds": "not configured",
    # `no record` was RESERVED, not implemented, and the reason it could not be
    # implemented was that the model could not tell "the source has no row for
    # this" apart from "nobody has looked". The extract manifest is what settled
    # it: a file with a system of record and a retrieval time was pulled, so an
    # absence in it is a recorded absence rather than an unexamined one.
    "no_record": "no record",
}


def render_coverage(panel):
    """Neutral by construction. Not a warning, and placed level with the groups.

    The counterpart to the work queue: that surface says what to go and get,
    this says what was not assessed at all.

    ABSENCE IS NEVER DIMMED. Each row carries a chip naming its kind, drawn at
    the same text weight as any asserted category and differing only by a dashed
    rule. Dimming an unknown, or shrinking it, says it matters less, which is the
    reading this tool exists to refuse.
    """
    with st.container(border=True):
        st.markdown(panel_head(panel.heading,
                               (badge(f"{len(panel.notes)} items"),)),
                    unsafe_allow_html=True)
        if panel.is_empty:
            note("Everything on this page was assessed.")
            return
        st.markdown(
            tight_table([(entry.count if entry.count else "",
                          absence_chip(entry.kind) + entry.sentence)
                         for entry in panel.notes]), unsafe_allow_html=True)
        counts = dash.coverage_counts(panel)
        if counts:
            # THE SENTENCES STAY AND THE BAR SITS UNDER THEM. A chart of what is
            # missing is a shape, not a statement: it cannot say WHICH KIND of
            # not-assessed each row is, and that distinction is the reason the
            # panel exists. The bar answers "which gap is biggest" and nothing
            # else, which is why it is sorted by count and says so.
            st.plotly_chart(count_bar(counts, hue="#9BA3AA"),
                            use_container_width=True, key="coverage-bar",
                            config={"displayModeBar": False})
            st.caption("Ordered by count. Every bar is a number of parts, and "
                       "the sentences above say which kind of unassessed each "
                       "one is.")


def absence_chip(kind):
    """A dashed chip naming the kind of absence, or nothing for an unknown kind.

    An unrecognised kind gets no chip rather than a guessed one, for the same
    reason the palette refuses to invent a colour: a wrong label on an absence is
    worse than no label, because the reader would act on it.
    """
    label = ABSENCE_LABEL.get(kind)
    return badge(label, absent=True) + " " if label else ""


def render_exposure(surface, find_out):
    st.title(surface.question)

    # WHAT THE SYSTEM DOES NOT KNOW LEADS. It is the most distinctive property
    # of this tool and it is invisible below the fold, so the coverage panel and
    # the outstanding fields come before any finding rather than after them.
    render_coverage(surface.coverage)

    if find_out.rows:
        st.subheader("Outstanding, on another page")
        settles = sum(len(row.detail["parts"]) for row in find_out.rows)
        note(f"{len(find_out.rows)} fields would settle {settles} undecided "
             f"memberships, listed on the "
             f"{view.SURFACE_TITLE[view.FIND_OUT]} page.")

    st.divider()
    st.subheader("Patterns")
    st.caption("Groups stacked vertically dominate the groups below them. "
               "Groups side by side are incomparable, and their left-to-right "
               "order is alphabetical and carries no meaning. Within a group, "
               f"parts are {ranking.DEFAULT_ORDER_LABEL}.")

    # The columns carry the partial order and nothing else: groups side by side
    # are incomparable. The findings themselves run full width underneath,
    # because a sentence squeezed into a quarter-width column wraps into a
    # ribbon and stops being readable prose, and the sentence is the deliverable.
    # ONE WIDTH FOR EVERY GROUP, whatever its layer holds. Sizing each layer to
    # its own group count gave a solo group the full page and a group with two
    # siblings a third of it, and the only thing that differed between them was
    # how many siblings they happened to have.
    width = view.lattice_width(surface.layers)
    for layer in surface.layers:
        columns = st.columns(width)
        for column, group in zip(columns, layer):
            with column:
                with st.container(border=True):
                    st.markdown(
                        panel_head(group.label, (
                            badge(f"{len(group.rows)} parts"),
                            badge(group.autonomy,
                                  open_style=group.autonomy == gov.RECOMMENDS),
                        )), unsafe_allow_html=True)
                    if group.autonomy == gov.RECOMMENDS:
                        st.caption("Recommended, not applied: this grouping "
                                   "depends on a modelling judgment.")
                    st.markdown(
                        identifier_block(row.key for row in group.rows),
                        unsafe_allow_html=True)

    sizes = dash.group_sizes(surface)
    if sizes:
        st.plotly_chart(count_bar(sizes), use_container_width=True,
                        key="group-sizes", config={"displayModeBar": False})
        st.caption("Members per group, in the order the lattice draws them and "
                   "NOT by size. Sorting this by count would contradict the "
                   "layout directly above it, which says these groups are "
                   "incomparable; a bar chart is a strong enough cue to "
                   "overrule a caption.")

    st.divider()
    render_findings(surface)
    render_blocking_matrix(surface)


def render_findings(surface):
    """Every exposed part once, whatever number of groups it belongs to.

    QA ISSUE-005: 36 findings and 36 evidence panels rendered for 21 parts,
    because the findings were emitted inside the layer loop and two archetypes
    hold identical membership. `SEA-P-0258` was explained three times, verbatim.

    THE LATTICE KEEPS THE MEMBERSHIP; THE FINDINGS MOVE OUT. The group panels
    above still show which parts sit in which archetype, and that is what
    encodes the dominance partial order, so nothing about the order is lost. A
    part legitimately belongs to several groups. What was duplicated was the
    explanation, and the explanation was never group-specific in the first
    place: `_part_row` builds the sentence from ALL of a part's archetype
    labels, so the two copies were identical by construction.

    THE ALTERNATIVE WAS WORSE. Rendering each part under the first group it
    appears in would have deduplicated just as well and made placement depend on
    iteration order, which CLAUDE.md rules out: a plausible default is read as a
    ranking, and "this part is filed under that archetype" is exactly the
    reading a reviewer would take.
    """
    rows = {}
    for row in surface.all_rows():
        if row.entity != view.PART:
            continue
        rows.setdefault(row.key, row)
    if not rows:
        return

    st.subheader("Findings")
    st.caption(f"One per exposed part, whatever number of groups it sits in. "
               f"Parts are {ranking.DEFAULT_ORDER_LABEL}, which carries no "
               f"meaning: reading order is not priority.")
    for key in ranking.in_default_order(rows):
        row = rows[key]
        finding(row.sentence + merge_marker(row.evidence))
        render_merges(row.evidence)
        render_evidence(row)


def render_blocking_matrix(surface):
    """Which finished goods each exposed part can stop.

    TOPOLOGY, NOT MAGNITUDE. Every mark is identical and a cell is present or
    absent, so nothing here reads as a quantity or a rank. A bar or a colour
    ramp in this position would encode magnitude across incommensurable units,
    which is the composite the arithmetic refuses, arriving through the picture.
    """
    parts = sorted({row.key for layer in surface.layers for group in layer
                    for row in group.rows})
    if not parts:
        return
    goods, matrix = view.blocking_matrix(parts, surface.evidence_by_part)
    st.subheader("What each part blocks")
    st.caption("A mark means the part appears in that finished good. Marks "
               "are identical: this is which, never how much.")
    note(f"{len(parts)} exposed parts, {len(goods)} finished goods.")
    # A HEATMAP OF A BINARY GRID, which is the same claim the marks made: a cell
    # is filled or it is not, and there is no middle value for a shade to carry.
    # The two-stop colour scale has exactly two stops for that reason.
    grid = [[1 if row.get(good) == view.MARK else 0 for row in matrix]
            for good in goods]
    figure = go.Figure(go.Heatmap(
        z=grid, x=[row["part"] for row in matrix], y=list(goods),
        colorscale=[[0, "#1B1F23"], [1, "#7FB2D9"]], showscale=False,
        xgap=1, ygap=1))
    chart_layout(figure, height=max(200, 40 * len(goods) + 120))
    st.plotly_chart(figure, use_container_width=True, key="blocking-matrix",
                    config={"displayModeBar": False})


CHART_BG = "rgba(0,0,0,0)"
CHART_GRID = "#262B30"
CHART_INK = "#9BA3AA"
CHART_SEQUENTIAL = ("#1E2933", "#2F4A5E", "#417089", "#5C93B4", "#7FB2D9")
# One hue per dimension. NOMINAL: the dimensions have no order, so neither does
# this list, and no hue here is darker or stronger than another by intent.
DIMENSION_HUE = {
    "lead_time_to_recover": "#7FB2D9",
    "blast_radius": "#C79BD9",
    "buffer_cover": "#7FD9C0",
    "portability": "#D9C27F",
    "concentration": "#D99B9B",
}


def chart_layout(figure, height=240):
    """One layout for every chart, so geometry never carries a difference."""
    figure.update_layout(
        height=height, margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor=CHART_BG, plot_bgcolor=CHART_BG,
        font=dict(color=CHART_INK, size=12),
        showlegend=False, bargap=0.08)
    figure.update_xaxes(gridcolor=CHART_GRID, zeroline=False)
    figure.update_yaxes(gridcolor=CHART_GRID, zeroline=False)
    return figure


def count_bar(pairs, hue="#7FB2D9", height=None):
    """A horizontal bar of (label, count). ONE UNIT, ALWAYS.

    Horizontal because the labels are archetype names and column names, and a
    vertical bar chart turns those into rotated text nobody reads. Largest at
    the top, which for a plotly category axis means reversing the list.
    """
    labels = [label for label, _ in pairs][::-1]
    counts = [count for _, count in pairs][::-1]
    figure = go.Figure(go.Bar(
        x=counts, y=labels, orientation="h", marker_color=hue,
        text=counts, textposition="outside",
        textfont=dict(color=CHART_INK, size=11), cliponaxis=False))
    chart_layout(figure, height=height or max(120, 34 * len(pairs) + 40))
    figure.update_xaxes(showgrid=True)
    figure.update_yaxes(showgrid=False)
    return figure


BASIS_HUE = {"supplier": "#7FB2D9", "region": "#C79BD9"}


def cluster_size_bar(rows):
    """Cluster sizes, coloured by grouping basis rather than by magnitude.

    One trace per basis, so the legend names both and neither is drawn as the
    other's competitor. A single undifferentiated ranking here would assert
    that a supplier cluster of six loses to a region cluster of twenty-eight,
    and those two are not answers to the same question.
    """
    figure = go.Figure()
    for basis, hue in BASIS_HUE.items():
        here = [(key, size) for key, size, this in rows if this == basis]
        if not here:
            continue
        figure.add_trace(go.Bar(
            x=[size for _k, size in here][::-1],
            y=[key for key, _s in here][::-1],
            orientation="h", name=f"by {basis}", marker_color=hue,
            text=[size for _k, size in here][::-1], textposition="outside",
            textfont=dict(color=CHART_INK, size=11), cliponaxis=False))
    chart_layout(figure, height=max(160, 26 * len(rows) + 60))
    figure.update_layout(showlegend=True, barmode="stack",
                         legend=dict(orientation="h", y=1.04,
                                     font=dict(size=11)))
    figure.update_yaxes(showgrid=False,
                        categoryorder="array",
                        categoryarray=[key for key, _s, _b in rows][::-1])
    return figure


def render_dashboard(result):
    """The overview surface.

    A FOURTH SURFACE, NOT A MERGER OF THE OTHER THREE. Each of those has one row
    entity and answers one question; this one has no row entity and answers none
    of them. It is an overview, and it links to the surfaces that decide.

    The encoding rule that would have forbidden every chart below was retired by
    the owner on 2026-08-06. CLAUDE.md and DESIGN.md record the decision and what
    it cost; this function does not re-argue it. What it does keep is the one
    rule that did not move: every chart draws ONE dimension in ONE unit, and
    nothing here puts two dimensions on one axis.
    """
    st.title("Dashboard")
    st.caption("An overview. Every decision is made on the other three "
               "surfaces, which this page links to and does not replace.")

    for column, tile in zip(st.columns(len(dash.tiles(result))),
                            dash.tiles(result)):
        # No delta. There is no previous run to compare against, and a delta
        # against nothing is an arrow pointing at a number that does not exist.
        column.metric(tile.label, f"{tile.value:,}", help=tile.of or None)
        if tile.of:
            # A NOTE, NOT A CAPTION. The denominator is a fact about the data,
            # and it changes with the dataset, so it is in the wrong register as
            # a caption. The contract test caught this on its first run against
            # this surface, which is the first thing it has caught that was not
            # already there.
            column.markdown(f"<p class='note'>{tile.of}</p>",
                            unsafe_allow_html=True)

    st.divider()
    render_region_map(result)
    st.divider()
    render_dimension_multiples(result)
    st.divider()
    render_incidence(result)


def render_region_map(result):
    st.subheader("Where the suppliers are")
    # THE MAP IS THE MOST BELIEVABLE THING ON THE PAGE, so it says what it is
    # before it says anything else. Four synthetic regions, no coordinates in
    # the data, and countries chosen as a drawing convention.
    note("The dataset has four regions and no coordinates. Countries are a "
         "drawing convention for those regions, not a claim that any supplier "
         "is in a particular country.")
    rows = dash.regions(result)
    frame = pd.DataFrame([
        {"country": country, "region": row.label,
         "suppliers": row.suppliers, "parts": row.parts,
         "exposed parts": row.exposed_parts}
        for row in rows for country in row.countries])
    figure = px.choropleth(
        frame, locations="country", locationmode="country names",
        color="exposed parts", hover_name="region",
        hover_data=["suppliers", "parts"],
        color_continuous_scale=list(CHART_SEQUENTIAL))
    figure.update_geos(bgcolor=CHART_BG, showframe=False, showcoastlines=False,
                       landcolor="#1B1F23", lakecolor=CHART_BG,
                       countrycolor=CHART_GRID, projection_type="natural earth")
    chart_layout(figure, height=380)
    figure.update_layout(coloraxis_colorbar=dict(title="exposed<br>parts"))
    # scrollZoom off: a geo plot captures the wheel, so scrolling the page over
    # the map zoomed the map instead and the page stayed put. Found by trying to
    # scroll past it.
    st.plotly_chart(figure, use_container_width=True,
                    config={"scrollZoom": False, "displayModeBar": False})

    st.dataframe(
        [{"region": row.label, "suppliers": row.suppliers,
          "parts with a supplier here": row.parts,
          "exposed parts": row.exposed_parts} for row in rows],
        hide_index=True, width="stretch")


def render_dimension_multiples(result):
    """Five charts, identical geometry, each in its own unit.

    IDENTICAL GEOMETRY IS STILL THE RULE HERE, and it is not a leftover. The
    dimensions do not commensurate, so a taller box or a wider axis would be a
    comparison the units do not support. Retiring the encoding rule allowed the
    charts; it did not make days and finished-good units the same thing.
    """
    st.subheader("The five dimensions, each in its own unit")
    st.caption("Five separate axes on purpose. No chart here puts two "
               "dimensions together, because there is no unit in which days "
               "and finished-good units are the same quantity.")

    series = dash.dimension_series(result)
    for chunk_start in range(0, len(series), 3):
        chunk = series[chunk_start:chunk_start + 3]
        # Padded to three so a row of two does not draw wider boxes than a row
        # of three, which would make width mean something again.
        for column, item in zip(st.columns(3), chunk):
            with column:
                st.markdown(f"###### {item.dimension.replace('_', ' ')}")
                st.plotly_chart(dimension_figure(item),
                                use_container_width=True,
                                key=f"dim-{item.dimension}")
                note(f"unit: {item.unit}. {item.assessed} assessed, "
                     f"{item.unknown} not established.")


def dimension_figure(item):
    hue = DIMENSION_HUE.get(item.dimension, "#7FB2D9")
    if item.is_categorical:
        figure = go.Figure(go.Bar(
            x=list(item.categories), y=list(item.categories.values()),
            marker_color=hue))
    elif item.values and isinstance(item.values[0], tuple):
        # A PAIRED MEASURE. Lead time carries (quoted, p95): both are days, so
        # both belong on this axis. Drawing only one would be the tool choosing
        # which half of the measure counts.
        figure = go.Figure()
        for index, (label, shade) in enumerate((("quoted", hue),
                                                ("p95", CHART_SEQUENTIAL[1]))):
            figure.add_trace(go.Histogram(
                x=[value[index] for value in item.values],
                name=label, marker_color=shade, opacity=0.75, nbinsx=24))
        # AFTER chart_layout, not before. chart_layout sets showlegend=False for
        # the single-series charts, so setting it here first meant the paired
        # chart drew two overlapping histograms with nothing saying which was
        # quoted and which was p95.
        chart_layout(figure)
        figure.update_layout(barmode="overlay", showlegend=True,
                             legend=dict(orientation="h", y=1.15,
                                         font=dict(size=11)))
        return figure
    else:
        figure = go.Figure(go.Histogram(x=list(item.values),
                                        marker_color=hue, nbinsx=24))
    return chart_layout(figure)


def render_incidence(result):
    parts, suppliers, grid = dash.incidence(result)
    st.subheader("Which supplier touches which exposed part")
    total_exposed = len(dash.exposed_parts(result))
    st.caption("A filled cell means that supplier appears on that part. The "
               "cell is present or absent; the shade carries nothing.")
    # NO SILENT CAP, AND THE TWO REASONS FOR A MISSING PART ARE NOT THE SAME
    # FACT. A part can be absent because the matrix is capped, or because it has
    # no supplier row at all, and the second is a finding rather than a display
    # limit: those are the parts with nobody to call. Reporting one count for
    # both would bury it.
    without_supplier = total_exposed - len(no_supplier_excluded := [
        part for part in dash.exposed_parts(result)
        if any(row[0] == part for row in dash.supplier_rows(result))])
    capped = len(no_supplier_excluded) - len(parts)
    note(f"{len(parts)} exposed parts drawn against {len(suppliers)} suppliers.")
    if without_supplier:
        note(f"{without_supplier} exposed parts have no supplier row at all, so "
             f"they are absent from this grid rather than drawn empty. That is "
             f"the finding, not a gap in the picture.")
    if capped > 0:
        note(f"{capped} further parts are not drawn: this grid is capped.")
    figure = go.Figure(go.Heatmap(
        z=grid, x=list(parts), y=list(suppliers),
        colorscale=[[0, "#1B1F23"], [1, "#7FB2D9"]], showscale=False,
        xgap=1, ygap=1))
    chart_layout(figure, height=max(320, 18 * len(suppliers)))
    st.plotly_chart(figure, use_container_width=True)


def render_find_out(surface):
    st.title(surface.question)
    st.caption("One row per field to fetch, not per part. Each row is one trip "
               "to one system of record.")
    if not surface.rows:
        st.write("Nothing is waiting on a missing field.")
    sizes = dash.field_sizes(surface)
    if sizes:
        st.plotly_chart(count_bar(sizes), use_container_width=True,
                        key="field-sizes", config={"displayModeBar": False})
        st.caption("Parts waiting on each field, largest first. This ordering "
                   "is a ranking and is meant to be: the page asks what to go "
                   "and get, and the answer is which single trip settles most.")
    for row in surface.rows:
        st.markdown(f"## `{row.key}`")
        finding(row.sentence)
        st.caption(ranking.DEFAULT_ORDER_LABEL)
        st.markdown(
            "<p class='note'>" +
            "  ".join(identifier(part) for part in row.detail["parts"]) +
            "</p>", unsafe_allow_html=True)


def render_confirm(surface, result):
    st.title(surface.question)
    st.caption("Every item here is a modelling judgment the system will not "
               "make alone, however complete the data is.")

    sizes = dash.cluster_sizes(result.report)
    if sizes:
        st.subheader("How much one decision covers")
        st.plotly_chart(cluster_size_bar(sizes), use_container_width=True,
                        key="cluster-sizes", config={"displayModeBar": False})
        st.caption("Members per cluster, largest first. A cluster is confirmed "
                   "as ONE act, so this is the size of the decision rather "
                   "than the size of the exposure. Supplier and region "
                   "groupings are coloured apart because they are not rivals: "
                   "they answer different questions, both can be true at once, "
                   "and no fact would settle one against the other.")

    grid = view.cluster_membership(result.report)
    if grid:
        st.subheader("Who sits with whom")
        st.caption("Identifiers only: nothing here is ordered or scored.")
        note(f"{len(grid)} exposed parts, with the supplier and the region "
             f"each one is grouped under.")
        st.dataframe(list(grid), hide_index=True, width="stretch")
    # Held outside the widget. This input exists only on this surface, so
    # Streamlit discards its state the moment a reviewer navigates away, and
    # they would come back anonymous with nothing on screen saying so.
    reviewer = st.sidebar.text_input(
        "Your name (recorded on every decision)",
        key="reviewer-input", value=st.session_state.get("reviewer", ""))
    st.session_state["reviewer"] = reviewer

    for row in surface.rows:
        st.markdown(f"## `{row.key}`")
        finding(row.sentence)
        if row.detail.get("members"):
            # The rendered sentence already names every member, so the list is
            # not repeated here. Saying it twice is the interface disagreeing
            # with itself about which one is the record.
            note(f"{row.detail['member_count']} members, confirmed as "
                 f"one act")
        control_columns = st.columns(len(row.controls) + 1)
        reason = control_columns[-1].selectbox(
            "Reason", row.controls[0].reason_codes, index=None,
            placeholder="Choose an option", key=f"reason-{row.key}")
        # `note_text`, NOT `note`. A bare `note` here binds a function-local name
        # for the whole of render_confirm and shadows the module-level note()
        # helper, so anything added below this line that calls note() raises
        # "TypeError: 'str' object is not callable" and points at itself rather
        # than at the collision forty lines above.
        note_text = st.text_input("Note", key=f"note-{row.key}")
        for column, control in zip(control_columns, row.controls):
            if column.button(control.action.title(), key=f"{control.action}-{row.key}"):
                try:
                    # THE CLOCK LIVES HERE, at the edge, and nowhere deeper.
                    # `actions.apply` requires `at` and has no default, so src/
                    # and every test stay deterministic and an undated decision
                    # is refused rather than silently stamped. Reading the time
                    # at the interface keeps the record real without putting a
                    # clock inside a module whose output is golden-pinned.
                    actions.apply(st.session_state.setdefault(
                        "log", gov.DecisionLog()), control, reviewer,
                        reason_code=reason or "", note=note_text,
                        at=datetime.now(timezone.utc).isoformat())
                    st.success(f"Recorded: {control.action} {row.key}")
                except ValueError as refusal:
                    st.warning(str(refusal))
        st.divider()

    render_decision_panel(st.session_state.get("log"), len(surface.rows))


def render_decision_panel(log, total_rows):
    """What this reviewer has decided, in the order they decided it.

    THE PANEL ASSEMBLES NO PROSE. Every sentence comes from the renderer: the
    event sentences from `render_all`, and the panel's own wording from the
    module's "wording with no event" section, where it is golden-pinned beside
    the coverage panel's. Writing these strings here is the shortest path and it
    would make the claim that this interface assembles nothing of its own false.

    NO CONTROL LIVES HERE. The log is append-only, so there is no undo and no
    delete, and a button in this panel would also shift the positional indices
    that three tests use to reach the cluster controls above.
    """
    events = list(log) if log is not None else []

    # No divider here: every cluster row above already closes with one, so adding
    # a second draws two rules a few pixels apart.
    st.subheader(govrender.DECISION_PANEL_HEADING)
    # The denominator first, which is how the exposure surface already works:
    # what is outstanding is the unknown, and it leads.
    note(govrender.decision_panel_count(
        len(events), max(total_rows - len(events), 0)))
    note(govrender.DECISION_PANEL_SCOPE)

    if not events:
        # Rendered BEFORE the first decision, so a reviewer meets the panel
        # before they need it rather than discovering it after.
        note(govrender.DECISION_PANEL_EMPTY)
        return

    st.caption(govrender.DECISION_PANEL_ORDER)
    for sentence in govrender.render_all(events):
        finding(sentence)


# Short names for navigation, with the question beneath. The questions stay as
# page headings where they carry the surface's purpose; in a sidebar a full
# sentence per item reads as prose rather than as navigation.
DASHBOARD = "dashboard"
NAV_NAME = {DASHBOARD: "Dashboard", view.EXPOSURE: "Exposure",
            view.FIND_OUT: "Find out", view.CONFIRM: "Confirm"}
NAV_SUBTITLE = {DASHBOARD: "the shape of the whole set",
                view.EXPOSURE: "what is worst",
                view.FIND_OUT: "what should I go and get",
                view.CONFIRM: "do I agree with your model"}

# THE CATEGORY PALETTE HAS NO HUE, AND THAT IS THE CORRECTION OF A REAL DEFECT.
#
# The previous revision drew each category at one HSL saturation and lightness,
# varying hue only, and called that the mathematical statement of "distinguishes
# but does not rank". HSL lightness is not perceptual lightness, so the claim was
# false: measured in CIELAB the six completeness entries spanned 15.3 L* points
# and sorted into a clean brightness ramp in declaration order. Three mechanisms
# asserted the guarantee (this file, config.toml, and a test) and all three
# checked the notation instead of the property, so their agreement read as
# confirmation while providing none.
#
# Nine of the eleven hues never reached a badge at all; only `executes` rendered.
# So the palette was a latent trap rather than a live defect: the first caller to
# write badge(row.completeness) would have shipped an ordered ramp with three
# guards saying it was fine.
#
# CLAUDE.md already settles it: "strip every colour and no information may be
# lost." If that holds, hue is redundant, and a channel that looks like an
# encoding while carrying nothing invites a reader to learn a mapping that is not
# there. One neutral chip. The label carries the category; form carries the rest.
REPO = "https://github.com/Lakshya2905/supplier-exposure-agent"

# One line, stated once, in the same register as everything else on the page.
# A reader who does not know the figures are one seed's synthetic data will read
# a count as a finding, which is the same mistake the README's seed note exists
# to prevent.
STANDING = (f"Demonstration on synthetic data. Figures are illustrative at "
            f"seed 42. Source: <a href='{REPO}'>{REPO.split('//')[1]}</a>")


def main():
    result, built = load()
    st.markdown(f"<p class='note'>{STANDING}</p>", unsafe_allow_html=True)
    st.sidebar.title("Supplier exposure")
    choice = st.sidebar.radio(
        "Surface",
        (DASHBOARD, view.EXPOSURE, view.FIND_OUT, view.CONFIRM),
        format_func=lambda name: f"**{NAV_NAME[name]}**  \n"
                                 f"{NAV_SUBTITLE[name]}")
    st.sidebar.caption("Three decision surfaces, deliberately separate. Their "
                       "rows are different things: a part, a field, a cluster. "
                       "The dashboard is an overview and decides nothing.")

    if choice == DASHBOARD:
        render_dashboard(result)
        return

    surface = built[choice]
    if choice == view.EXPOSURE:
        render_exposure(surface, built[view.FIND_OUT])
    elif choice == view.FIND_OUT:
        render_find_out(surface)
    else:
        render_confirm(surface, result)


main()
