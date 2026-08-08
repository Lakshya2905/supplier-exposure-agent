"""Serving the app to a real browser, and reading what it actually painted.

WHY THIS EXISTS. Four defects have now shipped that every test in this suite was
happy with, because every test in this suite reads the source and the browser
does not:

  the link colour     lost to Streamlit's own anchor rule at class specificity,
                      so links rendered in Streamlit's blue while the stylesheet
                      said accent and a test agreed with the stylesheet
  two ramp steps      `textColor` in config.toml beat the heading rules, so
                      `text-title` and `text-section` were never painted at all
  the map's slab      plotly's `geo.bgcolor` defaults to #fff and is covered by
                      neither paper_bgcolor nor plot_bgcolor
  every form field    drew its border in the same colour as its own fill, so no
                      field had a boundary

They are one failure, not four: **a declaration is not a painted pixel**, and
nothing that reads this repository can tell the two apart. So this module reads
`getComputedStyle` off a running page.

REQUIRED IN CI, SKIPPED LOCALLY, AND NEVER SILENTLY EITHER. A browser is a
150MB dependency and a contributor without one should still be able to run the
suite. But a check that skips quietly is worse than no check, because the gate
reports green either way. So `RENDER_CHECKS=required` turns a missing browser
into a failure, the gate workflow sets it, and `eval_harness.py` prints every
skip reason so a local run says out loud which controls did not run.
"""
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "review_app.py"

REQUIRED = os.environ.get("RENDER_CHECKS") == "required"
BOOT_TIMEOUT = 120
SURFACES = ("Dashboard", "Exposure", "Find out", "Confirm")


def playwright_or_skip():
    """The import, and the one place the skip-versus-fail rule is decided."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as missing:
        reason = (f"playwright is not installed ({missing}); rendered-page "
                  f"checks did not run. Install with `pip install -e \".[dev]\"`"
                  f" then `python -m playwright install chromium`.")
        if REQUIRED:
            raise AssertionError(
                f"RENDER_CHECKS=required and {reason}") from missing
        pytest.skip(reason, allow_module_level=True)
    return sync_playwright


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def serve():
    """Run the real app, the way a reviewer meets it.

    Not AppTest: AppTest never produces a document, which is precisely the layer
    where all four defects lived.
    """
    port = free_port()
    process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(APP),
         "--server.port", str(port), "--server.headless", "true",
         "--browser.gatherUsageStats", "false",
         "--server.fileWatcherType", "none"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    deadline = time.time() + BOOT_TIMEOUT
    while time.time() < deadline:
        if process.poll() is not None:
            raise AssertionError(
                f"the app exited before serving:\n{process.stdout.read()}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return process, f"http://127.0.0.1:{port}"
        except OSError:
            time.sleep(0.5)
    process.kill()
    raise AssertionError(f"the app did not serve within {BOOT_TIMEOUT}s")


def open_surface(page, url, name):
    """Load the app and select one surface, waiting for it to actually paint.

    Waits on a rendered element rather than on a timer. A fixed sleep passes on
    a fast machine and reports a blank page on a slow one, which would make this
    module the flaky check that gets ignored, and an ignored gate is the thing
    it was written to replace.
    """
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector('[data-testid="stSidebar"] [role="radiogroup"]',
                           timeout=60_000)
    page.wait_for_selector("h1", timeout=60_000)
    # THE RADIO IS CLICKED THROUGH THE DOM, not through Playwright's role
    # locator. Streamlit stacks a decorative div over the control, so a real
    # pointer click is intercepted and retried until it times out. Nothing about
    # that is a property of the app worth asserting: this module is here to read
    # what was painted, not to prove a label is clickable.
    page.evaluate(
        """(name) => {
            const label = [...document.querySelectorAll(
                '[role="radiogroup"] label')].find(
                    el => el.innerText.includes(name));
            if (!label) throw new Error('no surface named ' + name);
            (label.querySelector('input') || label).click();
        }""", name)
    page.wait_for_function(
        """(name) => {
            const label = [...document.querySelectorAll(
                '[role="radiogroup"] label')].find(
                    el => el.innerText.includes(name));
            return label && !!label.querySelector('input:checked');
        }""", arg=name, timeout=60_000)
    # Streamlit reruns the script on selection, so the previous surface is on
    # screen for a moment after the radio flips. Waiting for the network to
    # settle rather than for a fixed delay keeps this honest on a slow runner.
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)
    return page


# --------------------------------------------------------------- measuring --
# One script, run in the page, returning everything the assertions need. Reading
# it all in one pass keeps the browser round trips down and, more importantly,
# means every assertion is made against ONE render rather than against four.

PROBE = r"""
() => {
  const luminance = (r, g, b) => {
    const f = v => { v /= 255; return v <= 0.04045 ? v / 12.92
                                                  : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const parse = value => {
    const m = String(value).match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(',').map(Number);
    return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1};
  };
  const lum = value => { const c = parse(value); return c ? luminance(c.r, c.g, c.b) : null; };
  const opaqueBehind = el => {
    let node = el.parentElement;
    while (node) {
      const c = parse(getComputedStyle(node).backgroundColor);
      if (c && c.a > 0.9) return getComputedStyle(node).backgroundColor;
      node = node.parentElement;
    }
    return getComputedStyle(document.body).backgroundColor;
  };

  // Text colours actually painted, from HTML elements holding their own text.
  // Plotly draws SVG <text> with `fill`, which is a different channel and is
  // measured separately; the chart palette is not the text ramp.
  const painted = {};
  document.querySelectorAll('body *').forEach(el => {
    if (el.closest('.js-plotly-plot')) return;
    if (!Array.from(el.childNodes).some(n => n.nodeType === 3 && n.textContent.trim())) return;
    const colour = getComputedStyle(el).color;
    (painted[colour] = painted[colour] || []).push(
      (el.tagName + '.' + String(el.className || '')).slice(0, 60));
  });

  // Named elements, for the declared-versus-painted comparison.
  const sample = selector => {
    const el = document.querySelector(selector);
    if (!el) return null;
    const cs = getComputedStyle(el);
    return {colour: cs.color, decoration: cs.textDecorationLine,
            border: cs.borderTopWidth + ' ' + cs.borderTopColor,
            outline: cs.outlineStyle};
  };

  // Anything painted in the accent has to carry a second, non-colour cue.
  //
  // THE CUE IS LOOKED FOR ON THE CONTROL, not on every descendant. The first
  // version checked each text-bearing element on its own and flagged twenty-one
  // copies of Streamlit's expander chevron: an icon glyph inside a summary that
  // already carries an underline. It was reporting the caret for not having a
  // caret. WCAG 1.4.1 is about the actionable element, and a child of one
  // inherits its affordance along with its colour.
  const CONTROLS = 'a, button, summary, label, [role="radio"], [role="button"], [role="link"], [tabindex]';
  const cued = el => {
    const cs = getComputedStyle(el);
    return cs.textDecorationLine !== 'none' || cs.borderTopWidth !== '0px'
        || cs.borderBottomWidth !== '0px' || cs.borderLeftWidth !== '0px'
        || cs.outlineStyle !== 'none';
  };
  const accentish = [];
  document.querySelectorAll('body *').forEach(el => {
    if (el.closest('.js-plotly-plot')) return;
    if (!Array.from(el.childNodes).some(n => n.nodeType === 3 && n.textContent.trim())) return;
    const control = el.closest(CONTROLS);
    accentish.push({colour: getComputedStyle(el).color,
                    hasCue: cued(el) || (!!control && cued(control)),
                    insideAControl: !!control,
                    tag: el.tagName,
                    text: el.textContent.trim().slice(0, 30)});
  });

  // Form fields: the boundary, its own fill, and what is behind it.
  const fields = [];
  document.querySelectorAll('[data-testid="stTextInputRootElement"], [data-testid="stSelectbox"] [role="group"]')
    .forEach(el => {
      const cs = getComputedStyle(el);
      fields.push({border: cs.borderTopColor, width: cs.borderTopWidth,
                   fill: cs.backgroundColor, behind: opaqueBehind(el),
                   inSidebar: !!el.closest('[data-testid="stSidebar"]')});
    });

  // Every large opaque background OUTSIDE a chart. The generic form of the
  // map's white slab, restated so it does not depend on the substrate: the
  // original test asked whether anything large was LIGHT, which was only a
  // defect while the page was dark. What is actually wrong is a large area
  // painted a colour the design never declared, and the caller compares these
  // against the surfaces the stylesheet does declare.
  //
  // Charts are excluded rather than allowlisted: a bar is supposed to be a
  // colour that is not a surface, and enumerating every fill a chart may use
  // would be a second palette maintained by hand.
  const slabs = [];
  document.querySelectorAll('body *').forEach(el => {
    if (el.closest('.js-plotly-plot')) return;
    const box = el.getBoundingClientRect();
    if (box.width * box.height < 10000) return;
    const c = parse(getComputedStyle(el).backgroundColor);
    if (!c || c.a < 0.9) return;
    slabs.push({value: getComputedStyle(el).backgroundColor,
                area: Math.round(box.width * box.height),
                tag: el.tagName,
                testid: el.getAttribute('data-testid') || '',
                cls: String(el.className.baseVal ?? el.className ?? '').slice(0, 40)});
  });

  // Plotly geo subplots, for the defaults a stylesheet cannot reach.
  const geos = [];
  document.querySelectorAll('.js-plotly-plot').forEach(gd => {
    const geo = gd._fullLayout && gd._fullLayout.geo;
    if (!geo) return;
    const layer = sel => { const g = gd.querySelector(sel); return g ? g.querySelectorAll('path').length : 0; };
    geos.push({bgcolor: geo.bgcolor, showland: !!geo.showland,
               showcountries: !!geo.showcountries,
               landPaths: layer('.layer.land'), oceanPaths: layer('.layer.ocean'),
               filled: gd.querySelectorAll('.choroplethlocation').length,
               // India is drawn from vendored geometry as its own trace, so a
               // map with one trace is a map that lost it.
               traces: gd.data.filter(t => t.type === 'choropleth').length,
               customGeometry: gd.data.filter(t => !!t.geojson).length});
  });

  return {
    painted: Object.fromEntries(Object.entries(painted).map(([k, v]) => [k, v.slice(0, 3)])),
    named: {h1: sample('h1'), h2: sample('h2'), finding: sample('p.finding'),
            note: sample('p.note'), link: sample('a'),
            caption: sample('[data-testid="stCaptionContainer"] p'),
            summary: sample('[data-testid="stExpander"] summary')},
    accentish, fields, slabs, geos,
    pageBackground: getComputedStyle(document.body).backgroundColor
  };
}
"""


def measure(page, url, name):
    open_surface(page, url, name)
    return page.evaluate(PROBE)


def collect():
    """Every surface measured once, returned as {surface: probe}."""
    sync_playwright = playwright_or_skip()
    process, url = serve()
    try:
        with sync_playwright() as driver:
            browser = driver.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            readings = {name: measure(page, url, name) for name in SURFACES}
            browser.close()
        return readings
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()


def write_cache(path, readings):
    Path(path).write_text(json.dumps(readings))
