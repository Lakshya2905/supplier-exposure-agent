"""Build the frozen eval set. RUN BY HAND, ONCE. NEVER RUNS IN CI.

The rule, unchanged since stage 1 and relocated once at stage 4: eval
expectations are never produced by the generator under test, and never by the
analysis under test. This script is the one place the generator is allowed to
write something the gate later reads, and it is deliberately not wired into
anything: the harness does not import it, and CI does not call it.

Inputs, answer key and manifest are written together so they can be committed
together. Splitting that commit is exactly what lets them drift apart.

    python eval_build.py            # writes evals/ and its manifest
    python eval_build.py --check    # verify only, changes nothing

THE MANIFEST DETECTS AN EDIT. IT DOES NOT PREVENT ONE. A commit that rewrites a
frozen file and its manifest entry together passes this check, because the check
can only compare the set against its own record of itself. The control that
closes that hole is branch protection requiring the gate to be green before a
merge, which is enforced on a remote and is NOT in place for a purely local
repository. The limit is printed by the harness for the same reason it is
written here: a control nobody knows the shape of is worse than no control.
"""
import argparse
import json
import shutil
import sys

from src.frozen import (ANSWER_KEY, EVALS, INPUTS, MANIFEST, MANIFEST_LIMIT,
                        SEED, check_manifest, frozen_files, key_for, sha256)
from src.generate_data import generate
from src.synthetic.config import GeneratorConfig


def write_manifest():
    payload = {
        "seed": SEED,
        "files": {key_for(p, EVALS): sha256(p) for p in frozen_files()},
        "note": MANIFEST_LIMIT.replace("\n  ", " "),
    }
    MANIFEST.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def build():
    if EVALS.exists():
        shutil.rmtree(EVALS)
    INPUTS.mkdir(parents=True)
    generate(GeneratorConfig(seed=SEED), INPUTS, ANSWER_KEY)
    payload = write_manifest()
    print(f"froze {len(payload['files'])} files at seed {SEED}")
    for name in sorted(payload["files"]):
        print(f"  {name}")
    print("\nCommit evals/ in ONE commit. Inputs and expectations that land "
          "separately are how they drift apart.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="verify the manifest without writing anything")
    args = parser.parse_args(argv)
    if args.check:
        ok, problems = check_manifest()
        for problem in problems:
            print(f"  {problem}")
        print("manifest OK" if ok else "MANIFEST FAILED")
        return 0 if ok else 1
    build()
    return 0


if __name__ == "__main__":
    sys.exit(main())
