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

BOTH SURFACES. The first half serves `review_app.py`, which is where those four
defects were found. The second half serves the Next.js app in `web/`, which is
what actually ships and was measured by nothing in a browser until a pulsing
skeleton shipped on all six of its surfaces. See the section head below it.

REQUIRED IN CI, SKIPPED LOCALLY, AND NEVER SILENTLY EITHER. A browser is a
150MB dependency and a contributor without one should still be able to run the
suite. But a check that skips quietly is worse than no check, because the gate
reports green either way. So `RENDER_CHECKS=required` turns a missing browser
into a failure, the gate workflow sets it, and `eval_harness.py` prints every
skip reason so a local run says out loud which controls did not run.
"""
import json
import os
import re
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

# The h1 each surface renders, read from the model rather than retyped, so a
# reworded question moves the wait with it instead of hanging on a title that no
# longer exists.
# BOTH HALVES READ FROM THE MODEL, not retyped here. The nav LABEL used to be a
# literal in this file while the h1 came from the model, so the plain-language
# pass renamed "Find out" to "What to check" and every rendered-page check
# errored looking for a button that no longer exists. A rewording should move
# the wait with it, which it only does if neither end is a copy.
from src.interface.model import (OVERVIEW_TITLE,  # noqa: E402
                                 SURFACE_QUESTION, SURFACE_TITLE, SURFACES)


TITLES = {OVERVIEW_TITLE: OVERVIEW_TITLE,
          **{SURFACE_TITLE[key]: SURFACE_QUESTION[key] for key in SURFACES}}
SURFACE_NAMES = tuple(TITLES)


# ------------------------------------------------------- colour, measured --
# ONE COPY OF THE ARITHMETIC, imported by both test modules. It was two, and two
# implementations of one question disagree eventually: the one nobody looks at is
# the one that drifts. WCAG's relative luminance is the same formula whichever
# surface is being measured.


def parse(value):
    """An `rgb()` or `rgba()` string as a channel triple, or None."""
    numbers = re.findall(r"[\d.]+", value or "")
    return (tuple(int(float(n)) for n in numbers[:3])
            if len(numbers) >= 3 else None)


def luminance(channels):
    def linear(value):
        value /= 255
        return (value / 12.92 if value <= 0.04045
                else ((value + 0.055) / 1.055) ** 2.4)
    red, green, blue = (linear(channel) for channel in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(one, other):
    high, low = sorted((luminance(one), luminance(other)), reverse=True)
    return (high + 0.05) / (low + 0.05)


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


def await_port(port, process, what, timeout=BOOT_TIMEOUT):
    """Wait for a server to accept a connection, or say why it never did.

    The process is watched as well as the port, because a server that died on
    startup would otherwise be reported as a timeout, and the traceback that
    says what actually went wrong is sitting in its output.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            raise AssertionError(
                f"{what} exited before serving:\n{process.stdout.read()}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return f"http://127.0.0.1:{port}"
        except OSError:
            time.sleep(0.5)
    process.kill()
    raise AssertionError(f"{what} did not serve within {timeout}s")


def stop(*processes):
    for process in processes:
        process.terminate()
    for process in processes:
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()


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
    return process, await_port(port, process, "the app")


def open_surface(page, url, name):
    """Load the app and select one surface, waiting for it to actually paint.

    Waits on a rendered element rather than on a timer. A fixed sleep passes on
    a fast machine and reports a blank page on a slow one, which would make this
    module the flaky check that gets ignored, and an ignored gate is the thing
    it was written to replace.
    """
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_selector('[data-testid="stButtonGroup"]', timeout=60_000)
    page.wait_for_selector("h1", timeout=60_000)
    # THE RADIO IS CLICKED THROUGH THE DOM, not through Playwright's role
    # locator. Streamlit stacks a decorative div over the control, so a real
    # pointer click is intercepted and retried until it times out. Nothing about
    # that is a property of the app worth asserting: this module is here to read
    # what was painted, not to prove a label is clickable.
    page.evaluate(
        """(name) => {
            const control = document.querySelector(
                '[data-testid="stButtonGroup"]');
            const button = [...control.querySelectorAll('button, label')].find(
                el => el.innerText.trim() === name);
            if (!button) throw new Error('no surface named ' + name);
            button.click();
        }""", name)
    # WAIT FOR THIS SURFACE'S OWN TITLE. The previous condition was "an h1
    # exists and the page has some text", which the surface being navigated AWAY
    # from satisfies, so it returned the instant the click landed and the only
    # real wait was a fixed 1.5s. That is a flake with a slow runner's name on
    # it: CI failed two assertions once and passed the same commit on a retry,
    # which is precisely how a gate stops being believed.
    page.wait_for_function(
        """(expected) => {
            const h1 = document.querySelector('h1');
            return !!h1 && h1.textContent.trim() === expected;
        }""", arg=TITLES[name], timeout=60_000)
    page.wait_for_load_state("networkidle")

    # AND THEN WAIT FOR THE CHARTS. The title is server-rendered and plotly draws
    # afterwards in the client, so a surface can carry its own h1 while its map
    # does not exist yet. `networkidle` does not help: plotly drawing is not
    # network activity.
    #
    # CI caught this on a commit that changed one markdown file: "no map was
    # found on any surface". It is my own regression — removing the fixed 1.5s
    # sleep made the title wait honest and took away the slack that was hiding
    # this. A sleep that happens to be long enough is not a wait.
    #
    # The count has to be STABLE, not merely non-zero: plotly mounts plots one at
    # a time, so "at least one is ready" is satisfied by the first of seven.
    page.evaluate("() => { window.__plotCount = -1; window.__plotStable = 0; }")
    page.wait_for_function(
        """() => {
            const plots = [...document.querySelectorAll('.js-plotly-plot')];
            if (!plots.length || !plots.every(p => p._fullLayout)) {
                window.__plotStable = 0;
                return false;
            }
            if (window.__plotCount !== plots.length) {
                window.__plotCount = plots.length;
                window.__plotStable = 0;
                return false;
            }
            // AND THEN WAIT FOR THE GEO SUBPLOT'S OWN PAINT. `_fullLayout`
            // exists as soon as plotly has resolved the layout, and the geo
            // subplot builds its topology AFTER that: land, coastlines and the
            // filled locations all arrive later. CI failed here on a commit
            // that touched three frontend files and nothing the Streamlit map
            // can see, with "showland is on and no land was drawn" and zero
            // filled regions, and passed on the other run of the same commit.
            //
            // A pass that depends on which runner was faster is not a pass, and
            // the correct response is to wait for the thing being measured
            // rather than to retry. Plots with no geo subplot satisfy this
            // trivially, which is every plot on three of the four surfaces.
            const geoReady = plots.every(plot => {
                const geo = plot._fullLayout && plot._fullLayout.geo;
                if (!geo) return true;
                const land = plot.querySelectorAll('.layer.land path').length;
                const filled =
                    plot.querySelectorAll('.choroplethlocation').length;
                return (!geo.showland || land > 0) && filled > 0;
            });
            if (!geoReady) {
                window.__plotStable = 0;
                return false;
            }
            return ++window.__plotStable >= 3;
        }""", timeout=60_000, polling=250)
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
            readings = {name: measure(page, url, name)
                        for name in SURFACE_NAMES}
            browser.close()
        return readings
    finally:
        stop(process)


def write_cache(path, readings):
    Path(path).write_text(json.dumps(readings))


# ----------------------------------------------- the surface that ships --
# EVERYTHING ABOVE MEASURES STREAMLIT, WHICH IS NOT THE DELIVERABLE ANY MORE.
# docs/HANDOFF.md says so in as many words, and the consequence was that the app
# a reader actually opens was measured by nothing in a browser.
#
# THE DEFECT THAT PROVES IT. `web/components/States.tsx` rendered Carbon's
# `SkeletonText` and `SkeletonPlaceholder`, which resolve in the browser to
# `animation: 3s ease-in-out infinite cds--skeleton`. That pulse ran on all six
# surfaces for the whole of every load while DESIGN.md's Motion section was
# marked [SHIPPED] and claimed "zero transitions, zero animations, and zero
# keyframes, verified by source scan". The scan read this repository's own
# stylesheets and the animation came from inside the component library, where no
# source read can reach. `tests/test_web_motion.py` guards the component now and
# says plainly in its own docstring that it cannot see what a dependency
# injects. This is the half that can.
#
# TWO STATES PER SURFACE, AND THE FIRST ONE IS THE POINT. A skeleton exists only
# while data is in flight, so a probe that waits for the page to settle would
# have found nothing and reported a clean page. The first request each surface
# makes is therefore intercepted and the page measured WHILE IT IS PENDING,
# which is the state the defect lived in: 164 to 169 elements of shell and
# loading copy, against 552 to 1441 once the run arrives.
WEB = ROOT / "web"
NEXT = WEB / "node_modules" / ".bin" / "next"
WEB_BUILD = WEB / ".next"

# Next's first response after a cold start compiles nothing (the build is done),
# but the API scores a real dataset per surface, and a cold CI runner is slow.
WEB_BOOT_TIMEOUT = 180


def web_build_or_skip():
    """The second place the skip-versus-fail rule is decided, same rule.

    The frontend needs its dependencies installed and built, which is a larger
    ask than a browser and exactly as unreasonable to require of somebody
    running the Python suite. So it skips, loudly, and `RENDER_CHECKS=required`
    turns it into a failure in CI, where the gate workflow builds it.
    """
    for path, fix in ((NEXT, "npm ci"), (WEB_BUILD, "npm run build")):
        if path.exists():
            continue
        reason = (f"{path.relative_to(ROOT)} is missing; the rendered checks "
                  f"for the shipping frontend did not run. Build it with "
                  f"`cd web && {fix}`.")
        if REQUIRED:
            raise AssertionError(f"RENDER_CHECKS=required and {reason}")
        pytest.skip(reason, allow_module_level=True)


def web_routes():
    """The six surfaces, read from the component that defines them.

    Retyping them here is the mistake this module already made once on the
    Streamlit side: the nav label was a literal in this file while the title
    came from the model, so a rewording left every check hunting for a control
    that no longer existed. `Shell.tsx` holds the navigation, so the navigation
    is read from `Shell.tsx`.
    """
    source = (WEB / "components" / "Shell.tsx").read_text()
    block = source.split("const NAV = [", 1)[1].split("];", 1)[0]
    routes = tuple(re.findall(r"href:\s*'([^']+)'", block))
    if not routes:
        raise AssertionError(
            "no route was found in Shell.tsx's NAV; the parse has rotted and "
            "every check below would have measured nothing")
    return routes


def serve_web():
    """The frontend as it is deployed, in front of the real scoring API.

    THE BUILT APP, NOT `next dev`. Development mode mounts Next's own dev
    overlay, which draws and animates furniture that no reader will ever see, so
    a motion check against it would be measuring the toolchain. The built server
    is also what the Dockerfile and Vercel run.

    `NEXT_PUBLIC_API_BASE` is cleared rather than trusted: it is inlined at
    build time and would send the browser past the proxy the deployment uses,
    which is a different application from the one being measured.
    """
    api_port = free_port()
    api = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.api.main:app",
         "--host", "127.0.0.1", "--port", str(api_port)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        api_url = await_port(api_port, api, "the scoring API", WEB_BOOT_TIMEOUT)
        environment = {**os.environ, "SEA_API_URL": api_url,
                       "NODE_ENV": "production"}
        environment.pop("NEXT_PUBLIC_API_BASE", None)
        web_port = free_port()
        web = subprocess.Popen(
            [str(NEXT), "start", "-p", str(web_port)],
            cwd=WEB, env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    except BaseException:
        stop(api)
        raise
    try:
        return (api, web), await_port(web_port, web, "the frontend",
                                      WEB_BOOT_TIMEOUT)
    except BaseException:
        stop(api, web)
        raise


def settle(page):
    """Wait for the run to arrive and the document to stop changing.

    NOT A TIMER, for the reason the Streamlit half learned the hard way: a sleep
    that happens to be long enough on this machine reports a blank page on a
    slower one, and a flaky control is an ignored control. `aria-busy` is the
    page's own statement that it is still waiting, and the size of the document
    settling is the generic form of "the charts have drawn" that does not have
    to name a chart library.
    """
    page.wait_for_function(
        """() => !document.querySelector('[aria-busy="true"]')""",
        timeout=120_000)
    page.evaluate("() => { window.__seaSize = -1; window.__seaStable = 0; }")
    page.wait_for_function(
        """() => {
            const size = document.querySelectorAll('*').length;
            if (size !== window.__seaSize) {
                window.__seaSize = size;
                window.__seaStable = 0;
                return false;
            }
            return ++window.__seaStable >= 3;
        }""", timeout=120_000, polling=250)


WEB_PROBE = r"""
() => {
  // Charts are excluded from the text-colour reading for the same reason they
  // are on the Streamlit side: a mark is supposed to be a colour that is not a
  // text step, and SVG paints through `fill`, which is a different channel.
  const CHART = '.cds--cc--chart-wrapper, .js-plotly-plot, svg';

  // WHAT THE THEME ACTUALLY RESOLVES TO. There is no `:root` block of hex
  // values to read here: every colour in `web/` is a Carbon token, so the
  // declared set is whatever `--cds-*` resolves to in this document. Resolved
  // by asking the browser rather than by parsing, because a token may be
  // declared in any notation and only one of those is what gets painted.
  const probe = document.createElement('span');
  document.body.appendChild(probe);
  const tokens = {};
  for (const holder of [document.documentElement, document.body]) {
    const cs = getComputedStyle(holder);
    for (const name of cs) {
      if (!name.startsWith('--cds-')) continue;
      const raw = cs.getPropertyValue(name).trim();
      if (!raw) continue;
      probe.style.color = 'rgb(1, 2, 3)';
      probe.style.color = raw;
      const resolved = getComputedStyle(probe).color;
      if (resolved && resolved !== 'rgb(1, 2, 3)') {
        (tokens[resolved] = tokens[resolved] || []).push(name);
      }
    }
  }
  probe.remove();

  // EVERY ELEMENT AND BOTH PSEUDO-ELEMENTS. The skeleton's pulse was on the
  // element; a spinner's is as often on a `::before`, and neither is reachable
  // from any file in this repository.
  const animations = [];
  for (const el of document.querySelectorAll('*')) {
    for (const pseudo of [null, '::before', '::after']) {
      const cs = getComputedStyle(el, pseudo);
      if (!cs.animationName || cs.animationName === 'none') continue;
      animations.push({tag: el.tagName, pseudo: pseudo || 'element',
                       cls: String(el.className.baseVal ?? el.className ?? '')
                              .slice(0, 60),
                       text: (el.textContent || '').trim().slice(0, 40),
                       name: cs.animationName, duration: cs.animationDuration,
                       iterations: cs.animationIterationCount,
                       playState: cs.animationPlayState});
    }
  }

  // MOTION THIS APPLICATION DECLARED, separated from motion its component
  // library declares, by asking WHICH RULE said so rather than which element it
  // landed on. A computed transition cannot be attributed by looking at the
  // element: a table cell carries `.cds--structured-list-td` and `.sea-figure`
  // at once, and reading the second as ownership reports Carbon's 110ms colour
  // fade as this repository's. That is the same mistake as flagging an expander
  // chevron for having no chevron, one file over.
  //
  // Two places a rule can come from that no `.scss` scan would catch: the
  // compiled bundle, and a `style={{transition}}` prop, which lands in the
  // element's own inline style and in no stylesheet at all.
  const ownMotion = [];
  const moves = style =>
    (style.transitionDuration && style.transitionDuration !== '0s')
    || (style.animationName && style.animationName !== 'none')
    || !!style.transition || !!style.animation;
  const walk = rules => {
    for (const rule of rules) {
      if (rule.cssRules) { walk(rule.cssRules); continue; }
      if (!rule.style || !moves(rule.style)) continue;
      if (!/sea-/.test(rule.selectorText || '')) continue;
      ownMotion.push({where: 'stylesheet',
                      what: (rule.selectorText || '').slice(0, 80),
                      transition: rule.style.transition,
                      animation: rule.style.animation});
    }
  };
  for (const sheet of document.styleSheets) {
    try { walk(sheet.cssRules); } catch { /* cross-origin; none are ours */ }
  }
  document.querySelectorAll('*').forEach(el => {
    if (!el.style || !moves(el.style)) return;
    ownMotion.push({where: 'inline style', what: el.tagName + '.'
                      + String(el.className.baseVal ?? el.className ?? '')
                          .slice(0, 60),
                    transition: el.style.transition,
                    animation: el.style.animation});
  });

  const painted = {};
  document.querySelectorAll('body *').forEach(el => {
    if (el.closest(CHART)) return;
    if (!Array.from(el.childNodes).some(
          n => n.nodeType === 3 && n.textContent.trim())) return;
    const colour = getComputedStyle(el).color;
    (painted[colour] = painted[colour] || []).push(
      (el.tagName + '.' + String(el.className.baseVal ?? el.className ?? ''))
        .slice(0, 60));
  });

  const parse = value => {
    const m = String(value).match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(',').map(Number);
    return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1};
  };
  const opaqueBehind = el => {
    let node = el.parentElement;
    while (node) {
      const c = parse(getComputedStyle(node).backgroundColor);
      if (c && c.a > 0.9) return getComputedStyle(node).backgroundColor;
      node = node.parentElement;
    }
    return getComputedStyle(document.body).backgroundColor;
  };

  // FIELDS, AND ALL FOUR EDGES OF EACH. Carbon draws one: a 1px bottom rule and
  // nothing else, where Streamlit drew a box. A check that read `borderTop`
  // would report every field on this surface as having no boundary and be
  // wrong, so the sides are reported and the caller decides.
  //
  // A field smaller than two pixels in either direction is skipped. That is the
  // file input behind the upload button, which Carbon hides at 1x1 and replaces
  // with its own control: measured rather than named, because "visually hidden"
  // has more than one implementation and a size is what a reader cannot see.
  const fields = [];
  document.querySelectorAll(
    'input:not([type=checkbox]):not([type=radio]), select, textarea'
  ).forEach(el => {
    const box = el.getBoundingClientRect();
    if (box.width < 2 || box.height < 2) return;
    const cs = getComputedStyle(el);
    fields.push({
      tag: el.tagName,
      cls: String(el.className || '').slice(0, 60),
      sides: ['Top', 'Right', 'Bottom', 'Left'].map(side => ({
        side, width: cs['border' + side + 'Width'],
        colour: cs['border' + side + 'Color']})),
      fill: cs.backgroundColor, behind: opaqueBehind(el),
      width: Math.round(box.width), height: Math.round(box.height)});
  });

  return {
    elements: document.querySelectorAll('*').length,
    busy: !!document.querySelector('[aria-busy="true"]'),
    tokens, animations, ownMotion, fields,
    painted: Object.fromEntries(
      Object.entries(painted).map(([k, v]) => [k, v.slice(0, 3)])),
    pageBackground: getComputedStyle(document.body).backgroundColor,
  };
}
"""


#: The states each surface is read in. A reader who has asked their system for
#: less motion gets a different page from the same build, and the skeleton
#: exception in DESIGN.md rests entirely on that being true, so it is measured
#: rather than restated in prose.
REDUCED = "reduced motion"
STATES = ("loading", "settled", f"loading, {REDUCED}", f"settled, {REDUCED}")


def read_surfaces(browser, url, reduced):
    """One pass over every route, in one browser context.

    Returns `{route: {state: probe}}`, the state names carrying the preference
    the context was opened with, so a reading can never be read as the other one.
    """
    page = browser.new_page(
        viewport={"width": 1440, "height": 1000},
        reduced_motion="reduce" if reduced else "no-preference")
    held = {}

    def hold(route):
        if "loading" not in held:
            try:
                held["loading"] = page.evaluate(WEB_PROBE)
            except Exception as unreadable:      # reported, never swallowed
                held["loading"] = {"error": str(unreadable)}
        route.continue_()

    page.route("**/api/**", hold)
    suffix = f", {REDUCED}" if reduced else ""
    readings = {}
    for path in web_routes():
        held.clear()
        page.goto(url + path, wait_until="domcontentloaded")
        settle(page)
        readings[path] = {f"loading{suffix}": held.get("loading"),
                          f"settled{suffix}": page.evaluate(WEB_PROBE)}
    page.close()
    return readings


def collect_web():
    """Every surface measured in four states, from one boot.

    Returns `{route: {state: probe}}` over `STATES`.

    THE LOADING READING IS TAKEN FROM INSIDE A REQUEST. Playwright holds it open
    for as long as the handler runs, so the page is measured at a moment it is
    provably still waiting rather than at whatever moment the machine happened
    to be at. Without that the reading is a race: fast API, settled page,
    nothing measured, green gate.

    THE FIRST REQUEST THE PAGE MAKES, whatever it is for, and that is not a
    detail. Holding `/api/score` specifically was wrong on two surfaces: What
    changed waits on `/api/runs` and the Decision log waits on `/api/decisions`,
    so whether either was still loading when the score was held depended on
    which fetch won, and the check failed about one run in three. At the first
    request nothing has arrived yet, so every surface is in its initial state by
    construction.

    AND THE WHOLE THING TWICE, ONCE WITH REDUCED MOTION ASKED FOR. The loading
    state animates on purpose now, and DESIGN.md says in as many words that
    Carbon honouring `prefers-reduced-motion: reduce` "is the only reason this
    is a cost rather than an accessibility defect". A claim carrying an
    exception should not rest on somebody having looked once.
    """
    sync_playwright = playwright_or_skip()
    web_build_or_skip()
    processes, url = serve_web()
    try:
        with sync_playwright() as driver:
            browser = driver.chromium.launch()
            readings = {path: {} for path in web_routes()}
            for reduced in (False, True):
                for path, states in read_surfaces(browser, url,
                                                  reduced).items():
                    readings[path].update(states)
            browser.close()
        return readings
    finally:
        stop(*processes)
