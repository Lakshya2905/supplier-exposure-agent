"""Session-wide fixtures.

THE SUITE MUST NOT WRITE TO THE APP'S AUDIT TRAIL OR ITS RUN STORE. `tests/test_review_app.py`
drives the real Streamlit app, and the Confirm surface records decisions to
`decisions/decisions.jsonl` as they are made. Without this, running the suite
appended a decision by "Ada Lovelace" to the operator's live record, which is
the test fixture forging an entry in the log the product exists to be trusted
for.

Redirected here rather than inside individual tests, because the app resolves
the path itself and any test that reaches the Confirm buttons writes, including
ones added later that nobody thought about.

PER TEST, NOT PER SESSION. The first version shared one directory across the
run, and the moment the log persisted, a test that recorded a decision left it
lying in wait for every test after it: the empty-state assertion passed alone and
failed in the suite. Persistence is exactly the property that turns a shared
fixture directory into shared state.
"""
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True, scope="session")
def runs_go_somewhere_disposable():
    """The same rule as below, for the API's run store, at session scope.

    SESSION RATHER THAN PER TEST, and the difference is not carelessness. The
    decisions fixture is per test because a persisted decision left lying in
    wait is shared state: the empty-state assertion passed alone and failed in
    the suite. A run is not shared state in that way, since nothing asserts how
    many runs exist and every test fetches a run it recorded itself.

    What forces session scope is ordering. `unittest`'s `setUpClass` runs before
    any function-scoped fixture, so a class that scores once for all its tests
    would record that run against whatever directory was live at the time, which
    is the operator's. Session scope is set before collection reaches it.
    """
    scratch = Path(tempfile.mkdtemp(prefix="sea-runs-"))
    previous = os.environ.get("SEA_RUNS_DIR")
    os.environ["SEA_RUNS_DIR"] = str(scratch)
    yield scratch
    if previous is None:
        os.environ.pop("SEA_RUNS_DIR", None)
    else:
        os.environ["SEA_RUNS_DIR"] = previous


@pytest.fixture(autouse=True)
def decisions_go_somewhere_disposable():
    scratch = Path(tempfile.mkdtemp(prefix="sea-decisions-"))
    previous = os.environ.get("SEA_DECISIONS_DIR")
    os.environ["SEA_DECISIONS_DIR"] = str(scratch)
    yield scratch
    if previous is None:
        os.environ.pop("SEA_DECISIONS_DIR", None)
    else:
        os.environ["SEA_DECISIONS_DIR"] = previous
