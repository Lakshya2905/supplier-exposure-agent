"""DESIGN.md's Motion rules, for the surface that actually ships them.

WHY THIS EXISTS. The Motion section is marked [SHIPPED] and claimed the app has
"zero transitions, zero animations, and zero keyframes, verified by source
scan". The scan read this repository's own stylesheet, and the animation was
coming from the component library: `SkeletonText` and `SkeletonPlaceholder`
resolve in the browser to `animation: 3s ease-in-out infinite cds--skeleton`.
Measured on the deployed page, that pulse was live on all six surfaces while the
document said it did not exist.

WHAT THIS CATCHES, AND WHAT IT DOES NOT. It reads `web/` source for components
and declarations this repository controls. It cannot see what a dependency
injects, which is the gap that let the original claim stand -- only a rendered
page can, and `tests/rendered.py` measures the Streamlit surface rather than
this one. It is sufficient for the rule it names, because rendering a skeleton
is a thing this repository does in its own source, and it is not sufficient for
Motion as a whole. That gap is stated here rather than implied by a green test.
"""
import re
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"
SOURCES = sorted(p for p in WEB.rglob("*.tsx") if "node_modules" not in p.parts)
STYLES = sorted(p for p in WEB.rglob("*.scss") if "node_modules" not in p.parts)


def body(path):
    """The file with its comments stripped.

    This file and the component it guards both explain the construct they
    forbid, and the corrections log records that hazard twice: a system that
    refuses a concept by name contains that name in its own refusal.
    """
    text = path.read_text()
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"^\s*//.*$", "", text, flags=re.M)


class TestNothingInTheInterfaceAnimates(unittest.TestCase):

    def test_the_scan_has_something_to_read(self):
        # A scan that matches nothing passes forever, and this repository has
        # been bitten by that shape before.
        self.assertTrue(SOURCES, "no .tsx found; the glob has rotted")
        self.assertTrue(STYLES, "no .scss found; the glob has rotted")

    def test_no_surface_renders_a_skeleton(self):
        """"No entrance animation, no spinner, no pulse, no skeleton."

        Named for the defect it would have caught: `States.tsx` rendered two of
        Carbon's skeletons, so every surface pulsed for as long as a load took.
        """
        for path in SOURCES:
            with self.subTest(file=path.name):
                self.assertNotRegex(body(path), r"\bSkeleton[A-Za-z]*\b")

    def test_no_stylesheet_declares_an_animation(self):
        for path in STYLES:
            with self.subTest(file=path.name):
                self.assertNotRegex(body(path), r"@keyframes|\banimation\s*:")

    def test_no_stylesheet_declares_a_transition(self):
        """"The only permitted state change is instantaneous." """
        for path in STYLES:
            with self.subTest(file=path.name):
                self.assertNotRegex(body(path), r"\btransition\s*:")
