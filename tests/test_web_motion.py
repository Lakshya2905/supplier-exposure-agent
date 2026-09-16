"""DESIGN.md's Motion rules, for the surface that actually ships them.

WHY THIS EXISTS. The Motion section is marked [SHIPPED] and claimed the app has
"zero transitions, zero animations, and zero keyframes, verified by source
scan". The scan read this repository's own stylesheet, and the animation was
coming from the component library: `SkeletonText` and `SkeletonPlaceholder`
resolve in the browser to `animation: 3s ease-in-out infinite cds--skeleton`.
Measured on the deployed page, that pulse was live on all six surfaces while the
document said it did not exist.

THE SKELETON ASSERTION IS GONE, AND THE RULE WENT WITH IT. On 2026-09-16 the
owner permitted `SkeletonText` and `SkeletonPlaceholder` for the loading state,
on the record, because the v2 build prompt asks for them by name. This file
no longer forbids them -- the assertion was removed with the rule it enforced,
the same way the source scan behind the retired nominal-encoding rule was
removed with that one. It was NOT removed to make a red suite green: the rule
it tested no longer exists, and DESIGN.md records who retired it and when.

SO THE LOADING STATE ANIMATES, DELIBERATELY, and nothing here contradicts that.
What survives is narrower and still worth holding: this repository declares no
motion of its own anywhere in `web/`.

WHAT THIS CATCHES, AND WHAT IT DOES NOT. It reads `web/` source for declarations
this repository controls. It cannot see what a dependency injects, which is the
gap that let the original claim stand -- only a rendered page can, and
`tests/rendered.py` measures the Streamlit surface rather than this one. So a
future component that animates because Carbon says so will pass here exactly as
the skeletons once did. That gap is stated rather than implied by a green test.
"""
import re
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"
STYLES = sorted(p for p in WEB.rglob("*.scss") if "node_modules" not in p.parts)


def body(path):
    """The file with its comments stripped.

    This file explains the constructs it forbids, and the corrections log
    records that hazard twice: a system that refuses a concept by name contains
    that name in its own refusal.
    """
    text = path.read_text()
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"^\s*//.*$", "", text, flags=re.M)


class TestThisRepositoryDeclaresNoMotionOfItsOwn(unittest.TestCase):

    def test_the_scan_has_something_to_read(self):
        # A scan that matches nothing passes forever, and this repository has
        # been bitten by that shape before.
        self.assertTrue(STYLES, "no .scss found; the glob has rotted")

    def test_no_stylesheet_declares_an_animation(self):
        for path in STYLES:
            with self.subTest(file=path.name):
                self.assertNotRegex(body(path), r"@keyframes|\banimation\s*:")

    def test_no_stylesheet_declares_a_transition(self):
        """"The only permitted state change is instantaneous." """
        for path in STYLES:
            with self.subTest(file=path.name):
                self.assertNotRegex(body(path), r"\btransition\s*:")
