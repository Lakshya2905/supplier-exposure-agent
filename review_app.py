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
  /* An operational console: dense rows, aligned columns, high information per
     screen. Prose keeps a readable measure of its own; the CONTAINER does not,
     because tables need the width and capping the container wastes a third of
     the screen. */
  .block-container {
      max-width: 100%;
      padding: 1.4rem 2.2rem 3rem 2.2rem;
  }
  html, body, [class*="css"] { -webkit-font-smoothing: antialiased; }
  h1 {
      font-size: 1.3rem !important; font-weight: 600 !important;
      letter-spacing: -0.012em; margin: 0.5rem 0 0.55rem 0 !important;
      padding: 0 !important; color: #16181A; line-height: 1.3;
  }
  h2 {
      font-size: 0.92rem !important; font-weight: 600 !important;
      text-transform: uppercase; letter-spacing: 0.06em; color: #4A4E52;
      margin: 1.35rem 0 0.4rem 0 !important; padding: 0 !important;
      line-height: 1.4;
  }
  h3, h4, h5, h6 {
      font-size: 0.84rem !important; font-weight: 600 !important;
      margin: 0.85rem 0 0.3rem 0 !important; padding: 0 !important;
      line-height: 1.4;
  }
  hr, [data-testid="stDivider"] hr {
      border: none; border-top: 1px solid #E2E0D9; margin: 1rem 0 0.7rem 0;
  }
  [data-testid="stVerticalBlock"] { gap: 0.5rem; }
  p, li { line-height: 1.42; }
  p.finding {
      font-size: 0.94rem; line-height: 1.45; max-width: 96ch;
      margin: 0.55rem 0 0.1rem 0; color: #16181A;
  }
  p.note {
      font-size: 0.82rem; line-height: 1.42; max-width: 96ch;
      color: #4A4E52; margin: 0 0 0.3rem 0;
  }
  .stCaption, [data-testid="stCaptionContainer"] p {
      font-size: 0.76rem !important; color: #63676B !important;
      line-height: 1.4; max-width: 100ch; margin-bottom: 0.35rem !important;
  }
  code, .identifier, .ids span {
      font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas,
                   monospace;
      font-size: 0.79rem; background: transparent !important;
      color: #16181A !important; padding: 0 !important;
  }
  /* Membership as a dense block. Fourteen parts occupy three lines, not
     fourteen, and the fixed width keeps them in columns. */
  .ids { display: flex; flex-wrap: wrap; gap: 0 0.9rem; margin: 0.15rem 0 0 0; }
  .ids span { display: inline-block; min-width: 6.4rem; line-height: 1.5; }
  /* Coverage: counts right-aligned against their sentence, one glance. */
  table.tight { border-collapse: collapse; width: 100%; }
  table.tight td {
      border-top: 1px solid #EDEBE4; padding: 0.22rem 0.7rem 0.22rem 0;
      font-size: 0.82rem; line-height: 1.4; color: #4A4E52; vertical-align: top;
  }
  table.tight td.num {
      text-align: right; width: 4rem; font-variant-numeric: tabular-nums;
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      color: #16181A; white-space: nowrap;
  }
  [data-testid="stExpander"],
  [data-testid="stExpander"] details,
  [data-testid="stExpanderDetails"] {
      border: none !important; border-radius: 0 !important;
      box-shadow: none !important; background: transparent !important;
  }
  [data-testid="stExpander"] { margin: 0 0 0.55rem 0; }
  [data-testid="stExpander"] summary {
      font-size: 0.78rem !important; color: #2C4A63 !important;
      padding: 0 !important; width: max-content;
  }
  [data-testid="stExpander"] summary p { font-size: 0.78rem !important; }
  [data-testid="stExpanderDetails"] {
      border-left: 1px solid #E2E0D9 !important;
      padding: 0.3rem 0 0.1rem 0.9rem !important; margin-top: 0.35rem;
  }
  [data-testid="stDataFrame"], [data-testid="stTable"] {
      border-radius: 0 !important; box-shadow: none !important;
  }
  /* Grid cells are identifiers and counts, so they are set in monospace with
     tabular figures: columns line up and a number reads as a number. This is
     the console reference, and it is typography rather than encoding. */
  [data-testid="stDataFrame"] [role="gridcell"],
  [data-testid="stDataFrame"] [role="columnheader"] {
      font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas,
                   monospace !important;
      font-size: 0.78rem !important;
      font-variant-numeric: tabular-nums;
  }
  .stButton > button {
      border-radius: 2px; border: 1px solid #2C4A63; background: transparent;
      color: #2C4A63; font-size: 0.78rem; font-weight: 500;
      padding: 0.18rem 0.8rem; box-shadow: none;
  }
  .stButton > button:hover {
      background: #2C4A63; color: #FCFCFA; border-color: #2C4A63;
  }
  section[data-testid="stSidebar"] {
      background: #F2F1ED; border-right: 1px solid #E2E0D9; width: 15rem !important;
  }
  section[data-testid="stSidebar"] .block-container { padding: 1.6rem 1rem; }
  /* Navigation reads as a deliberate list rather than a form control. */
  section[data-testid="stSidebar"] [role="radiogroup"] { gap: 0 !important; }
  section[data-testid="stSidebar"] [role="radiogroup"] > label {
      padding: 0.28rem 0 0.28rem 0.6rem; margin: 0;
      border-left: 2px solid transparent;
  }
  section[data-testid="stSidebar"] [role="radiogroup"] > label:has(input:checked) {
      border-left-color: #2C4A63; background: #E7E5DE;
  }
  section[data-testid="stSidebar"] [role="radiogroup"] > label > div:first-child {
      display: none;
  }
  section[data-testid="stSidebar"] [role="radiogroup"] p {
      font-size: 0.82rem !important; line-height: 1.3;
  }
  /* ------------------------------------------------- panels and badges --
     Bordered panels and surface fills carry STRUCTURE: where one group ends
     and the next begins. Badges carry CATEGORY.

     EVERY BADGE IS THE SAME COLOUR AND THE SAME WEIGHT, and that is a
     correctness constraint rather than a stylistic one. The moment one badge
     is red and another green, the set has an order, and an ordered encoding
     across incommensurable states is the composite this system refuses to
     compute arriving through the palette. The label carries the meaning; the
     chip only says "this is a label". The single exception is autonomy, where
     filled versus outlined distinguishes two categories without ranking them,
     mirroring the rule that an executed finding has nothing to click. */
  .badge {
      display: inline-block; font-family: ui-monospace, SFMono-Regular, Menlo,
      Consolas, monospace; font-size: 0.68rem; letter-spacing: 0.04em;
      text-transform: uppercase; padding: 0.08rem 0.4rem; border-radius: 2px;
      background: #E7E5DE; color: #4A4E52; border: 1px solid #DAD7CE;
      margin-right: 0.3rem; vertical-align: 0.06rem; white-space: nowrap;
  }
  .badge.open { background: transparent; color: #2C4A63; border-color: #2C4A63; }
  [data-testid="stVerticalBlockBorderWrapper"] {
      border: 1px solid #E2E0D9 !important; border-radius: 3px;
      background: #FFFFFF;
  }
  [data-testid="stVerticalBlockBorderWrapper"] > div { padding: 0.55rem 0.7rem; }
  .panelhead {
      display: flex; align-items: baseline; gap: 0.5rem; flex-wrap: wrap;
      border-bottom: 1px solid #EDEBE4; margin: -0.55rem -0.7rem 0.5rem -0.7rem;
      padding: 0.4rem 0.7rem; background: #F7F6F2;
  }
  .panelhead .title { font-size: 0.86rem; font-weight: 600; color: #16181A; }
  .navglyph {
      font-family: ui-monospace, Menlo, monospace; color: #8A8E92;
      margin-right: 0.4rem;
  }
  [data-testid="stMetric"], [data-testid="stAlert"] {
      border-radius: 0 !important; box-shadow: none !important;
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


def badge(text, open_style=False):
    """A nominal chip. Same colour for every category, always."""
    return f"<span class='badge{' open' if open_style else ''}'>{text}</span>"


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


def render_coverage(panel):
    """Neutral by construction. Not a warning, and placed level with the groups.

    The counterpart to the work queue: that surface says what to go and get,
    this says what was not assessed at all.
    """
    with st.container(border=True):
        st.markdown(panel_head(panel.heading,
                               (badge(f"{len(panel.notes)} items"),)),
                    unsafe_allow_html=True)
        if panel.is_empty:
            note("Everything on this page was assessed.")
            return
        st.markdown(
            tight_table([(entry.count if entry.count else "", entry.sentence)
                         for entry in panel.notes]), unsafe_allow_html=True)


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
    reviewer = st.sidebar.text_input("Your name (recorded on every decision)")

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
            "Reason", ("",) + row.controls[0].reason_codes,
            key=f"reason-{row.key}")
        note = st.text_input("Note", key=f"note-{row.key}")
        for column, control in zip(control_columns, row.controls):
            if column.button(control.action.title(), key=f"{control.action}-{row.key}"):
                try:
                    actions.apply(st.session_state.setdefault(
                        "log", gov.DecisionLog()), control, reviewer,
                        reason_code=reason, note=note)
                    st.success(f"Recorded: {control.action} {row.key}")
                except ValueError as refusal:
                    st.warning(str(refusal))
        st.divider()


# Nominal marks, one per surface. They distinguish, they do not rank.
NAV_GLYPH = {view.EXPOSURE: "▤", view.FIND_OUT: "◷", view.CONFIRM: "◆"}

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
        format_func=lambda name: f"{NAV_GLYPH[name]}  "
                                 f"{view.SURFACE_QUESTION[name]}")
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
