"""Generate the synthetic data set.

    python -m src.generate_data --seed 42

Builds a clean, fully consistent world, then applies messiness as explicit
damage, recording every decision into an answer key. Files are written only at
the end, from a complete in-memory model, so a crash cannot leave the CSVs and
the answer key describing different worlds.

The generator also accepts an explicit config, which is how targeted edge cases
get constructed on demand instead of fishing for a seed that happens to contain
one.
"""
import argparse
import random
import sys
from pathlib import Path

from .synthetic import truth as truth_mod
from .synthetic import writers
from .synthetic.build import build_clean_world
from .synthetic.config import GeneratorConfig
from .synthetic.messiness import apply_messiness

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "data"
DEFAULT_TRUTH = ROOT / "truth" / "answer_key.json"


def generate(config=None, out_dir=None, truth_path=None):
    """Build and write. Returns (world, truth) for callers that want to assert
    against the model rather than re-read the CSVs."""
    config = config or GeneratorConfig()
    out_dir = Path(out_dir) if out_dir else DEFAULT_OUT
    truth_path = Path(truth_path) if truth_path else DEFAULT_TRUTH

    # One explicitly threaded Random. No module-level seeding, so importing
    # this module never reaches into anyone else's random state.
    rng = random.Random(config.seed)

    world = build_clean_world(rng, config)
    answer_key = truth_mod.Truth(
        seed=config.seed, config_hash=truth_mod.config_hash(config))
    apply_messiness(rng, config, world, answer_key)
    truth_mod.assign_verdicts(world, answer_key)

    writers.write_world(world, out_dir)
    truth_mod.write(answer_key, truth_path)
    return world, answer_key


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m src.generate_data",
        description="Generate the synthetic supplier exposure data set.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out-dir", default=None,
                        help="where the CSVs go (default: ./data)")
    parser.add_argument("--truth-path", default=None,
                        help="where the answer key goes "
                             "(default: ./truth/answer_key.json)")
    args = parser.parse_args(argv)

    config = GeneratorConfig(seed=args.seed)
    world, answer_key = generate(config, args.out_dir, args.truth_path)

    out = Path(args.out_dir) if args.out_dir else DEFAULT_OUT
    print(f"seed {config.seed} -> {out}")
    print(f"  parts          {len(world.parts)}")
    print(f"  bom edges      {len(world.bom)}")
    print(f"  suppliers      {len(world.suppliers)}")
    print(f"  supplier links {len(world.links)}")
    print(f"  lead times     {len(world.lead_times)}")
    print(f"  finished goods {len(world.finished_goods)}, "
          f"{len(world.demand)} with demand")
    print("  verdicts:")
    for verdict, count in sorted(truth_mod.verdict_coverage(answer_key).items()):
        print(f"    {verdict:28} {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
