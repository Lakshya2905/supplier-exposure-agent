"""The review interface, split so the claims are testable without a UI.

STREAMLIT PAINTS; IT DOES NOT DECIDE. Same shape as agent 1's "LangGraph
orchestrates; it does not think". `model.py` computes a view model out of plain
data with no Streamlit import anywhere, `actions.py` turns a reviewer's click
into a decision event, and `review_app.py` renders what it is given.

The reason is not tidiness. This is the stage where the autonomy claims either
become visible or silently stop existing: everything the system knows about who
may decide what is currently a property of an object, and on screen it becomes
layout. If an executed finding and a recommends finding render identically, five
stages of ceiling discipline evaporate at the moment a person looks at the
output. Keeping the model pure makes that a property assertable as data rather
than something inferred from a screenshot.
"""
