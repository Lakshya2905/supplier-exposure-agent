"""Streamlit review interface. It paints the view model and decides nothing.

THREE SURFACES, NEVER ONE TABLE. Each answers a different question for a
different person at a different moment, and each has a different row entity: a
part, a field, a cluster. A unified view has to pick one, and the other two get
denormalised. That is not a preference; flattening clusters to parts would make
a reviewer confirm one judgment once per member and would empty `member_count`
of meaning.

WIDGETS THAT ENCODE MAGNITUDE AS LENGTH OR FRACTION ARE BANNED. `st.progress`,
progress and bar-chart column configs, multi-series charts and colour ramps are
all normalised scales by construction, which is the composite arriving through a
widget rather than through arithmetic. `tests/test_review_app.py` enforces the
list by scanning this file.

AUTONOMY IS AN AFFORDANCE. Rows that execute get no button. That is checked in
the model, which refuses to construct such a row, and again here.
"""
import streamlit as st

from src import governance as gov
from src import ranking
from src.interface import actions
from src.interface import model as view
from src.pipeline import default_data_dir, run, surfaces

st.set_page_config(page_title="Supplier exposure review", layout="wide")

# An operational console: SAP, an MRP screen, a procurement terminal. Dense
# rows, aligned columns, monospace identifiers, high information per screen.
# Bordered panels and surface fills carry structure; badges carry category.
#
# NOTHING HERE ENCODES A MAGNITUDE, and that is a correctness constraint rather
# than a stylistic one. Every badge is one colour and one weight, because a set
# where one chip is red and another green has an order, and an ordered encoding
# across incommensurable states is the composite this system refuses to compute
# arriving through the palette instead of the arithmetic. The accent appears
# only on things a reviewer can act on.
CONSOLE_CSS = """
<style>
  /* Middle density. The earlier revision read as an essay and the one after it
     read as congested; this sits between them. Where a region felt crowded the
     fix was usually less on screen at once rather than more air, so the panels
     carry the map and the sentences below carry the reading. */
  .block-container { max-width: 100%; padding: 1.6rem 2.4rem 4rem 2.4rem; }
  html, body, [class*="css"] { -webkit-font-smoothing: antialiased; }

  h1 {
      font-size: 1.34rem !important; font-weight: 600 !important;
      letter-spacing: -0.01em; margin: 0.5rem 0 0.7rem 0 !important;
      padding: 0 !important; color: #F0F2F4; line-height: 1.35;
  }
  h2 {
      font-size: 0.9rem !important; font-weight: 600 !important;
      text-transform: uppercase; letter-spacing: 0.08em; color: #8FA0AD;
      margin: 1.9rem 0 0.6rem 0 !important; padding: 0 !important;
      line-height: 1.45;
  }
  h3, h4, h5, h6 {
      font-size: 0.85rem !important; font-weight: 600 !important;
      color: #C7CDD3;
      margin: 1.1rem 0 0.4rem 0 !important; padding: 0 !important;
      line-height: 1.45;
  }
  hr, [data-testid="stDivider"] hr {
      border: none; border-top: 1px solid #2C3237; margin: 1.5rem 0 1.1rem 0;
  }
  [data-testid="stVerticalBlock"] { gap: 0.7rem; }
  p, li { line-height: 1.5; color: #D5DADE; }

  p.finding {
      font-size: 0.94rem; line-height: 1.58; max-width: 104ch;
      margin: 0.9rem 0 0.15rem 0; color: #E3E6E8;
  }
  p.note {
      font-size: 0.83rem; line-height: 1.5; max-width: 104ch;
      color: #9BA3AA; margin: 0 0 0.45rem 0;
  }
  .stCaption, [data-testid="stCaptionContainer"] p {
      font-size: 0.78rem !important; color: #838C94 !important;
      line-height: 1.5; max-width: 104ch; margin-bottom: 0.45rem !important;
  }
  a, a:visited { color: #7FB2D9; }

  code, .identifier, .ids span {
      font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas,
                   monospace;
      font-size: 0.79rem; background: transparent !important;
      color: #C9D2D9 !important; padding: 0 !important;
  }
  .ids { display: flex; flex-wrap: wrap; gap: 0.1rem 1.1rem; margin: 0.3rem 0 0 0; }
  .ids span { display: inline-block; min-width: 6.6rem; line-height: 1.75; }

  table.tight { border-collapse: collapse; width: 100%; }
  table.tight td {
      border-top: 1px solid #262B30; padding: 0.36rem 0.8rem 0.36rem 0;
      font-size: 0.83rem; line-height: 1.5; color: #B6BEC5; vertical-align: top;
  }
  table.tight tr:first-child td { border-top: none; }
  table.tight td.num {
      text-align: right; width: 4rem; font-variant-numeric: tabular-nums;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      color: #E3E6E8; white-space: nowrap;
  }

  [data-testid="stExpander"],
  [data-testid="stExpander"] details,
  [data-testid="stExpanderDetails"] {
      border: none !important; border-radius: 0 !important;
      box-shadow: none !important; background: transparent !important;
  }
  [data-testid="stExpander"] { margin: 0 0 0.8rem 0; }
  [data-testid="stExpander"] summary {
      font-size: 0.79rem !important; color: #7FB2D9 !important;
      padding: 0 !important; width: max-content;
  }
  [data-testid="stExpander"] summary p { font-size: 0.79rem !important; }
  [data-testid="stExpanderDetails"] {
      border-left: 1px solid #2C3237 !important;
      padding: 0.5rem 0 0.2rem 1rem !important; margin-top: 0.5rem;
  }

  [data-testid="stDataFrame"], [data-testid="stTable"] {
      border-radius: 2px !important; box-shadow: none !important;
  }
  [data-testid="stDataFrame"] [role="gridcell"],
  [data-testid="stDataFrame"] [role="columnheader"] {
      font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas,
                   monospace !important;
      font-size: 0.78rem !important; font-variant-numeric: tabular-nums;
  }

  .stButton > button {
      border-radius: 3px; border: 1px solid #3E5C74; background: #1E2933;
      color: #9CC6E3; font-size: 0.79rem; font-weight: 500;
      padding: 0.24rem 0.9rem; box-shadow: none;
  }
  .stButton > button:hover {
      background: #2A3B49; color: #D6E8F5; border-color: #7FB2D9;
  }

  section[data-testid="stSidebar"] {
      background: #101315; border-right: 1px solid #262B30;
      width: 16rem !important;
  }
  section[data-testid="stSidebar"] .block-container { padding: 1.8rem 1.1rem; }
  section[data-testid="stSidebar"] [role="radiogroup"] { gap: 0 !important; }
  section[data-testid="stSidebar"] [role="radiogroup"] > label {
      padding: 0.5rem 0 0.5rem 0.7rem; margin: 0;
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
      font-size: 0.82rem !important; line-height: 1.45; color: #8B949C;
  }
  section[data-testid="stSidebar"] [role="radiogroup"] strong {
      color: #DDE3E8; font-weight: 600;
  }

  /* ------------------------------------------------- panels and badges --
     Surfaces and borders carry structure: where one group ends and the next
     begins. Hue on a chip carries CATEGORY.

     THE PALETTE IS NOMINAL BY ARITHMETIC. Every chip is drawn at one
     saturation and one lightness and differs only in hue, and the hues are
     confined to a cool band, because a set can be perfectly equal in weight
     and still rank if one member is the colour of an alarm. There is no
     red-amber-green here and no warm-to-cool progression: an ordered colour
     encoding across incommensurable states is the composite this system
     refuses to compute, arriving through the palette instead of the
     arithmetic. Autonomy keeps a filled-versus-outlined distinction, which
     separates two categories without ranking them. */
  /* 12px is the floor. The previous 0.68rem (10.9px) uppercase monospace with
     0.05em tracking applied the slowest reading mode, letter by letter with no
     word shape, to the densest label in the interface, and a long category name
     would have truncated. A truncated epistemic state is a wrong claim rather
     than a cosmetic problem, so the chip wraps instead. */
  .badge {
      display: inline-block; font-size: 0.75rem; font-weight: 500;
      letter-spacing: 0.02em; padding: 0.1rem 0.45rem; border-radius: 3px;
      background: #242A30; color: #D5DADE; border: 1px solid #333B42;
      margin-right: 0.35rem; vertical-align: 0.06rem;
  }
  .badge.open {
      background: transparent; color: #7FB2D9; border-color: #3E5C74;
  }
  /* Absence is the same footprint and the same text weight as presence. The
     dashed rule is the only difference, and it is a form cue, so it survives
     greyscale and print where a colour cue would not. */
  .badge.absent { border-style: dashed; border-color: #6B7278; }
  [data-testid="stVerticalBlockBorderWrapper"] {
      border: 1px solid #272D33 !important; border-radius: 4px;
      background: #191D21;
  }
  [data-testid="stVerticalBlockBorderWrapper"] > div { padding: 0.7rem 0.9rem; }
  .panelhead {
      display: flex; align-items: baseline; gap: 0.55rem; flex-wrap: wrap;
      border-bottom: 1px solid #272D33; margin: -0.7rem -0.9rem 0.7rem -0.9rem;
      padding: 0.55rem 0.9rem; background: #1E242A;
      border-radius: 4px 4px 0 0;
  }
  .panelhead .title { font-size: 0.88rem; font-weight: 600; color: #E3E6E8; }

  [data-testid="stMetric"], [data-testid="stAlert"] {
      border-radius: 3px !important; box-shadow: none !important;
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


def render_evidence(row):
    """Read-only workings, one click away. There is no control in here.

    A conclusion a reviewer cannot check is a conclusion they have to trust, and
    trust is what this system replaces with verification.
    """
    evidence = row.evidence
    with st.expander("How this was worked out"):
        st.caption("Read only. Nothing on this panel changes any value.")

        st.markdown("###### Supplier rows read for this part")
        if evidence.supplier_rows:
            st.dataframe(
                [{"supplier as spelled in suppliers.csv": r.supplier_name,
                  "region": r.region,
                  "lead time on file": "yes" if r.has_lead_time else "no",
                  "quoted days": r.quoted_lead_time_days,
                  "p95 days": r.p95_lead_time_days}
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
              "contribution": r.contribution or "not counted"}
             for r in evidence.demand_rows],
            hide_index=True, width="stretch")

        st.markdown("###### Lead time record used")
        used = evidence.lead_time_used
        note(
            f"{identifier(used.supplier_name)}, "
            f"{used.quoted_lead_time_days} days quoted, "
            f"{used.p95_lead_time_days} at p95."
            if used else
            "None. No supplier on this part has a lead time record.")

        for line in evidence.notes:
            note(line)

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
    for layer in surface.layers:
        columns = st.columns(len(layer)) if len(layer) > 1 else [st.container()]
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

        for group in layer:
            for row in group.rows:
                finding(row.sentence)
                render_evidence(row)
        st.divider()

    render_blocking_matrix(surface)


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
    st.caption(f"A mark means the part appears in that finished good. "
               f"{len(parts)} exposed parts, {len(goods)} finished goods. "
               f"Marks are identical: this is which, never how much.")
    st.dataframe(
        list(matrix), hide_index=True, width="stretch",
        column_config={"part": st.column_config.TextColumn("part", width=110)})


def render_find_out(surface):
    st.title(surface.question)
    st.caption("One row per field to fetch, not per part. Each row is one trip "
               "to one system of record.")
    if not surface.rows:
        st.write("Nothing is waiting on a missing field.")
    for row in surface.rows:
        st.markdown(f"## `{row.key}`")
        finding(row.sentence)
        st.caption(row.detail["order_label"])
        st.markdown(
            "<p class='note'>" +
            "  ".join(identifier(part) for part in row.detail["parts"]) +
            "</p>", unsafe_allow_html=True)


def render_confirm(surface, result):
    st.title(surface.question)
    st.caption("Every item here is a modelling judgment the system will not "
               "make alone, however complete the data is.")

    grid = view.cluster_membership(result.report)
    if grid:
        st.subheader("Who sits with whom")
        st.caption(f"{len(grid)} exposed parts, with the supplier and the "
                   f"region each one is grouped under. Identifiers only: "
                   f"nothing here is ordered or scored.")
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
            st.caption(f"{row.detail['member_count']} members, confirmed as "
                       f"one act")
        control_columns = st.columns(len(row.controls) + 1)
        reason = control_columns[-1].selectbox(
            "Reason", row.controls[0].reason_codes, index=None,
            placeholder="Choose an option", key=f"reason-{row.key}")
        note = st.text_input("Note", key=f"note-{row.key}")
        for column, control in zip(control_columns, row.controls):
            if column.button(control.action.title(), key=f"{control.action}-{row.key}"):
                try:
                    actions.apply(st.session_state.setdefault(
                        "log", gov.DecisionLog()), control, reviewer,
                        reason_code=reason or "", note=note)
                    st.success(f"Recorded: {control.action} {row.key}")
                except ValueError as refusal:
                    st.warning(str(refusal))
        st.divider()


# Short names for navigation, with the question beneath. The questions stay as
# page headings where they carry the surface's purpose; in a sidebar a full
# sentence per item reads as prose rather than as navigation.
NAV_NAME = {view.EXPOSURE: "Exposure", view.FIND_OUT: "Find out",
            view.CONFIRM: "Confirm"}
NAV_SUBTITLE = {view.EXPOSURE: "what is worst",
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
        (view.EXPOSURE, view.FIND_OUT, view.CONFIRM),
        format_func=lambda name: f"**{NAV_NAME[name]}**  \n"
                                 f"{NAV_SUBTITLE[name]}")
    st.sidebar.caption("Three surfaces, deliberately separate. Their rows are "
                       "different things: a part, a field, a cluster.")

    surface = built[choice]
    if choice == view.EXPOSURE:
        render_exposure(surface, built[view.FIND_OUT])
    elif choice == view.FIND_OUT:
        render_find_out(surface)
    else:
        render_confirm(surface, result)


main()
