"""Paths and integrity checks for the frozen eval set. No generator here.

Deliberately separate from `eval_build.py`. The harness needs the paths and the
manifest check; it must not be able to reach the generator, even transitively,
because the rule since stage 1 is that eval expectations are never produced by
the thing under test. Importing the builder for its constants would have made
`generate()` reachable from the gate, which is the hole rather than the rule.
`tests/test_eval_integrity.py` asserts the separation holds.
"""
import hashlib
import json
from pathlib import Path

EVALS = Path("evals")
INPUTS = EVALS / "inputs"
ANSWER_KEY = EVALS / "answer_key.json"
MANIFEST = EVALS / "MANIFEST.json"
SEED = 42

MANIFEST_LIMIT = (
    "The manifest DETECTS an edit to a frozen file. It does not PREVENT one: a\n"
    "  commit that rewrites a frozen file and its manifest entry together passes\n"
    "  this check, because the check compares the set against its own record of\n"
    "  itself. Branch protection requiring this gate to be green before a merge\n"
    "  is the control that closes it, and that applies on a remote only. It is\n"
    "  NOT in place for a purely local repository."
)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen_files(root=None):
    root = Path(root) if root else EVALS
    inputs = root / "inputs"
    key = root / "answer_key.json"
    found = sorted(inputs.glob("*.csv")) if inputs.exists() else []
    if key.exists():
        found.append(key)
    return sorted(found, key=str)


def key_for(path, root):
    """Manifest keys are relative to the eval root, so the check works from any
    working directory and from a copy of the tree."""
    return Path(path).relative_to(root).as_posix()


def check_manifest(root=None):
    """Returns (ok, problems). Never raises on a mismatch."""
    root = Path(root) if root else EVALS
    manifest = root / "MANIFEST.json"
    if not manifest.exists():
        return False, [f"{manifest} does not exist; run `python eval_build.py`"]
    recorded = json.loads(manifest.read_text())["files"]
    problems = []
    for name, expected in sorted(recorded.items()):
        path = root / name
        if not path.exists():
            problems.append(f"missing: {name}")
        elif sha256(path) != expected:
            problems.append(f"edited: {name}")
    for path in frozen_files(root):
        if key_for(path, root) not in recorded:
            problems.append(f"untracked: {key_for(path, root)}")
    return not problems, problems
