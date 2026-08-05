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
from src.pipeline import run, surfaces

st.set_page_config(page_title="Supplier exposure review", layout="wide")

# A printed diligence memo, not a dashboard. Left aligned and pinned to a
# readable measure rather than centred in the viewport; hierarchy from size and
# weight alone; hairline rules instead of shadows; no cards, no badges, no
# icons. Nothing here encodes a value: the single accent appears only on things
# a reviewer can act on, because a coloured number is an ordinal encoding by
# implication and those are refused everywhere else in this system.
MEMO_CSS = """
<style>
  .block-container {
      max-width: 60rem;
      margin-left: 3.5rem;
      margin-right: auto;
      padding-top: 2.2rem;
      padding-bottom: 4rem;
  }
  html, body, [class*="css"] {
      font-feature-settings: "kern" 1, "liga" 1;
      -webkit-font-smoothing: antialiased;
  }
  h1 {
      font-size: 1.45rem !important;
      font-weight: 600 !important;
      letter-spacing: -0.012em;
      margin: 0 0 0.15rem 0 !important;
      padding: 0 !important;
      color: #16181A;
  }
  h2 {
      font-size: 0.98rem !important;
      font-weight: 600 !important;
      letter-spacing: -0.005em;
      margin: 2rem 0 0.8rem 0 !important;
      padding: 0 !important;
  }
  h3, h4 {
      font-size: 0.9rem !important;
      font-weight: 600 !important;
      margin: 1.1rem 0 0.35rem 0 !important;
      padding: 0 !important;
  }
  hr, [data-testid="stDivider"] hr {
      border: none;
      border-top: 1px solid #E2E0D9;
      margin: 1.4rem 0 0.9rem 0;
  }
  [data-testid="stVerticalBlock"] { gap: 0.35rem; }
  /* The finding sentence is the deliverable, so it reads as body copy rather
     than as a cell in a grid. */
  p.finding {
      font-size: 1.0rem;
      line-height: 1.62;
      max-width: 78ch;
      margin: 1.05rem 0 0.15rem 0;
      color: #16181A;
  }
  p.note {
      font-size: 0.86rem;
      line-height: 1.55;
      max-width: 74ch;
      color: #4A4E52;
      margin: 0 0 0.7rem 0;
  }
  .stCaption, [data-testid="stCaptionContainer"] p {
      font-size: 0.79rem !important;
      color: #63676B !important;
      line-height: 1.5;
      max-width: 74ch;
  }
  code, .identifier {
      font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas,
                   monospace;
      font-size: 0.86em;
      background: transparent !important;
      color: #16181A !important;
      padding: 0 !important;
  }
  /* Flat, hairline, no card. */
  [data-testid="stExpander"],
  [data-testid="stExpander"] details,
  [data-testid="stExpanderDetails"] {
      border: none !important;
      border-radius: 0 !important;
      box-shadow: none !important;
      background: transparent !important;
  }
  [data-testid="stExpander"] { margin: 0 0 1.5rem 0; }
  [data-testid="stExpander"] summary {
      font-size: 0.82rem !important;
      color: #2C4A63 !important;
      padding: 0 !important;
      width: max-content;
  }
  [data-testid="stExpander"] summary p { font-size: 0.82rem !important; }
  [data-testid="stExpanderDetails"] {
      border-left: 1px solid #E2E0D9 !important;
      padding: 0.4rem 0 0.2rem 1rem !important;
      margin-top: 0.5rem;
  }
  [data-testid="stDataFrame"], [data-testid="stTable"] {
      border-radius: 0 !important;
      box-shadow: none !important;
  }
  .stButton > button {
      border-radius: 2px;
      border: 1px solid #2C4A63;
      background: transparent;
      color: #2C4A63;
      font-size: 0.82rem;
      font-weight: 500;
      padding: 0.25rem 0.9rem;
      box-shadow: none;
  }
  .stButton > button:hover {
      background: #2C4A63;
      color: #FCFCFA;
      border-color: #2C4A63;
  }
  section[data-testid="stSidebar"] {
      background: #F2F1ED;
      border-right: 1px solid #E2E0D9;
  }
  section[data-testid="stSidebar"] .block-container {
      margin-left: 0;
      padding-top: 2.4rem;
  }
  [data-testid="stMetric"], [data-testid="stAlert"] {
      border-radius: 0 !important;
      box-shadow: none !important;
  }
</style>
"""
st.markdown(MEMO_CSS, unsafe_allow_html=True)


def identifier(text):
    return f"<span class='identifier'>{text}</span>"


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
    result = run()
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
    st.subheader(panel.heading)
    if panel.is_empty:
        note("Everything on this page was assessed.")
        return
    for entry in panel.notes:
        note(entry.sentence)


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
                st.markdown(f"**{group.label}**")
                st.caption(f"{len(group.rows)} parts")
                if group.autonomy == gov.RECOMMENDS:
                    st.caption("Recommended, not applied: this grouping "
                               "depends on a modelling judgment.")
                st.markdown(
                    "<p class='note'>" +
                    "<br>".join(identifier(row.key) for row in group.rows) +
                    "</p>", unsafe_allow_html=True)

        for group in layer:
            for row in group.rows:
                finding(row.sentence)
                render_evidence(row)
        st.divider()


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


def main():
    result, built = load()
    st.sidebar.title("Supplier exposure")
    choice = st.sidebar.radio(
        "Surface",
        (view.EXPOSURE, view.FIND_OUT, view.CONFIRM),
        format_func=lambda name: view.SURFACE_QUESTION[name])
    st.sidebar.caption(
        "Three surfaces, deliberately separate. They answer different "
        "questions and their rows are different things: a part, a field, a "
        "cluster.")

    surface = built[choice]
    if choice == view.EXPOSURE:
        render_exposure(surface, built[view.FIND_OUT])
    elif choice == view.FIND_OUT:
        render_find_out(surface)
    else:
        render_confirm(surface, result)


main()
