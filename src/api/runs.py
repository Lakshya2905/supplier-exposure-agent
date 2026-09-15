"""Where a run goes so that a link to it still works tomorrow.

WHAT IS STORED IS THE INPUT, NEVER THE ANSWER. A run record holds the CSVs it
was given, a digest of each, and when it happened. `GET /api/run/{id}` scores
them again rather than replaying a saved payload, and the reasons are the same
two the decision log gives for storing structure and rendering prose:

  a wording change reaches a run recorded last month, because the sentence is
  produced now and was never frozen into the record

  a scoring change SHOWS UP as a changed answer on an old run, instead of the
  record quietly disagreeing with the code that claims to have produced it

The cost is real and is accepted: re-scoring is about a second, and a run is
not reproducible if its inputs are deleted from under it. The alternative is a
saved answer nobody can check, which is the thing this project exists not to
ship.

DIGESTS ARE PROVENANCE, NOT INTEGRITY. They say which bytes were scored, so a
reader can tell two runs of "the same" file apart. They do not prevent an edit,
in exactly the way `evals/MANIFEST.json` does not: a record rewritten together
with its digest agrees with itself. Said here so nobody reads more into them.
"""
import hashlib
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

# REDIRECTABLE, matching `governance.store`'s DECISIONS_ENV for the same reason:
# a test run must not leave runs in an operator's live directory.
RUNS_ENV = "SEA_RUNS_DIR"

RECORD = "run.json"
INPUTS = "inputs"


def runs_dir():
    return Path(os.environ.get(RUNS_ENV, "runs"))


def new_id():
    """A random id, not a sequence number.

    A sequential id would be a count of runs, and a count published in a URL is
    read as a measure of activity by everybody who sees it.
    """
    return uuid.uuid4().hex[:12]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def record_run(source_dir, dataset, run_id=None, at=None, copy_inputs=True):
    """Copy the inputs beside a record of what they were, and return the record.

    `copy_inputs=False` is for a dataset already committed in this repository:
    `evals/`, `demo/` and `data/` are not going anywhere, and copying a frozen
    eval set into a runs directory would make a second copy of the one thing
    that is supposed to have exactly one.
    """
    source_dir = Path(source_dir)
    run_id = run_id or new_id()
    at = at or datetime.now(timezone.utc).isoformat()
    directory = runs_dir() / run_id
    directory.mkdir(parents=True, exist_ok=True)

    if copy_inputs:
        target = directory / INPUTS
        target.mkdir(parents=True, exist_ok=True)
        for path in sorted(source_dir.glob("*.csv")):
            shutil.copy2(path, target / path.name)
        data_dir = target
    else:
        data_dir = source_dir

    record = {
        "id": run_id,
        "created_at": at,
        "dataset": dataset,
        "data_dir": str(data_dir),
        # ONE ENTRY PER FILE, with its size, so "which bytes were scored" is
        # answerable without the file. Sorted, so two records of the same inputs
        # compare equal rather than differing by directory iteration order.
        "files": [{"name": path.name, "sha256": sha256(path),
                   "bytes": path.stat().st_size}
                  for path in sorted(Path(data_dir).glob("*.csv"))],
    }
    (directory / RECORD).write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def load_run(run_id):
    """The record, or None. Never a partially reconstructed one."""
    path = runs_dir() / run_id / RECORD
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_runs():
    """Every run, newest first, by recorded time rather than by file mtime.

    EXPLICIT KEY, NEVER DIRECTORY ORDER. `iterdir` is arbitrary today and
    becomes a meaningful order the moment a filesystem changes how it iterates,
    at which point a list acquires a ranking nobody chose.
    """
    directory = runs_dir()
    if not directory.exists():
        return []
    records = [load_run(child.name) for child in directory.iterdir()
               if child.is_dir()]
    return sorted([r for r in records if r],
                  key=lambda record: (record["created_at"], record["id"]),
                  reverse=True)
