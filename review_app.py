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
from src.interface import actions
from src.interface import model as view
from src.pipeline import run, surfaces

st.set_page_config(page_title="Supplier exposure review", layout="wide")


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
    with st.expander(f"How this was worked out: {row.key}"):
        st.caption("Read only. Nothing on this panel changes any value.")

        st.markdown("**Supplier rows read for this part**")
        if evidence.supplier_rows:
            st.dataframe(
                [{"supplier (as spelled in suppliers.csv)": r.supplier_name,
                  "region": r.region,
                  "lead time on file": "yes" if r.has_lead_time else "no",
                  "quoted days": r.quoted_lead_time_days,
                  "p95 days": r.p95_lead_time_days}
                 for r in evidence.supplier_rows],
                hide_index=True, width="stretch")
        else:
            st.write("No supplier rows exist for this part.")

        st.markdown("**Finished goods and quantities behind the usage figure**")
        st.dataframe(
            [{"finished good": r.finished_good,
              "qty per finished good": r.qty_per_finished_good,
              "annual units": ("absent from the demand plan"
                               if r.annual_units is None else r.annual_units),
              "contribution": r.contribution or "not counted"}
             for r in evidence.demand_rows],
            hide_index=True, width="stretch")

        st.markdown("**Lead time record used**")
        used = evidence.lead_time_used
        st.write(
            f"{used.supplier_name}: {used.quoted_lead_time_days} days quoted, "
            f"{used.p95_lead_time_days} at p95."
            if used else
            "None. No supplier on this part has a lead time record.")

        for note in evidence.notes:
            st.write(f"- {note}")

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
        st.write("Everything on this page was assessed.")
        return
    for note in panel.notes:
        st.write(f"- {note.sentence}")


def render_exposure(surface):
    st.title(surface.question)
    st.caption("Groups stacked vertically dominate the groups below them. "
               "Groups side by side are incomparable, and their left-to-right "
               "order is alphabetical and carries no meaning.")
    for notice in surface.notices:
        st.info(notice)

    for layer in surface.layers:
        columns = st.columns(len(layer)) if len(layer) > 1 else [st.container()]
        for column, group in zip(columns, layer):
            with column:
                st.subheader(group.label)
                st.caption(f"{len(group.rows)} parts, {group.order_label}")
                if group.autonomy == gov.RECOMMENDS:
                    st.caption("Recommended, not applied: this grouping "
                               "depends on a modelling judgment.")
                for row in group.rows:
                    st.write(row.sentence)
                    render_evidence(row)
        st.divider()

    render_coverage(surface.coverage)


def render_find_out(surface):
    st.title(surface.question)
    st.caption("One row per field to fetch, not per part. Each row is one trip "
               "to one system of record.")
    if not surface.rows:
        st.write("Nothing is waiting on a missing field.")
    for row in surface.rows:
        st.subheader(row.key)
        st.write(row.sentence)
        st.caption(row.detail["order_label"])
        st.dataframe([{"part": part} for part in row.detail["parts"]],
                     hide_index=True, width="stretch")


def render_confirm(surface, result):
    st.title(surface.question)
    st.caption("Every item here is a modelling judgment the system will not "
               "make alone, however complete the data is.")
    reviewer = st.sidebar.text_input("Your name (recorded on every decision)")

    for row in surface.rows:
        st.subheader(row.key)
        st.write(row.sentence)
        if row.detail.get("members"):
            st.caption(f"{row.detail['member_count']} members, confirmed as "
                       f"one act")
            st.dataframe([{"part": part} for part in row.detail["members"]],
                         hide_index=True, width="stretch")
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
        render_exposure(surface)
    elif choice == view.FIND_OUT:
        render_find_out(surface)
    else:
        render_confirm(surface, result)


main()
