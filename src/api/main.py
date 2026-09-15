"""The scoring library over HTTP. A wrapper, and deliberately nothing more.

WHAT THIS FILE IS ALLOWED TO DO. Read a request, call `pipeline.run`, encode the
answer, write a decision through `interface.actions`. What it is NOT allowed to
do is decide anything: no threshold, no default, no coercion, no fallback value.
Every judgment in this system has a home already, and an HTTP layer is the most
tempting place to put a second one, because the caller is remote and a 200 with
a plausible number is easier than an error that says what is missing.

So the refusals stay where they are and this file surfaces them. A decision with
no decider is refused by `actions.apply`, not here. A verdict comes from
`identify`, not here. If a rule appears to be missing at this layer, it is
because it is enforced one layer down, which is where a test can reach it.

RE-SCORED, NEVER REPLAYED. `GET /api/run/{id}` scores the stored inputs again
rather than returning a saved payload. See `runs.py` for why.
"""
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel

from .. import binding
from .. import governance as gov
from .. import scoring
from ..governance import store
from ..governance.render import VERDICT_PROSE
from ..interface import actions
from ..interface import dashboard as dash
from ..interface import model as view
from ..pipeline import DEMO_DIR, WORKING_DIR, run, surfaces
from ..recovery import RECOVERY_INPUTS_FILE
from . import runs
from .encode import encode

# The files a run is scored from. `recovery_inputs.csv` is optional and the rest
# are not, and that distinction is the reader's to enforce rather than this
# file's: `pipeline.run` opens each one and fails on a missing required file.
# Named here so an upload can be checked against a list somebody can read.
REQUIRED_FILES = ("bom.csv", "part_master.csv", "demand_plan.csv",
                  "suppliers.csv", "lead_times.csv", "sources.csv")
OPTIONAL_FILES = (RECOVERY_INPUTS_FILE,)

# Datasets already in this repository, by name. A caller naming one of these
# gets it scored without uploading anything, which is what lets a cold frontend
# render something real on first load.
BUILT_IN = {
    "demo": DEMO_DIR,
    "working": WORKING_DIR,
    "frozen": Path("evals/inputs"),
}
DEFAULT_DATASET = "demo"

app = FastAPI(title="Supplier Exposure Agent", version="2.0")

# The frontend is served from a different origin in every environment this will
# run in. Kept to GET and POST, which is every verb this API has: there is no
# write path to source data, so there is nothing to PUT or DELETE.
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=False,
    allow_methods=["GET", "POST"], allow_headers=["*"])

# A whole run is a couple of megabytes of JSON, because it carries the evidence
# for every part and evidence is the point. Compression is transport, not
# summary: nothing is dropped to make it smaller, which is the version of this
# that would have cost something.
app.add_middleware(GZipMiddleware, minimum_size=1024)


# --------------------------------------------------------------- payloads --

def _counts(result):
    """The run context strip's figures, computed from the same scores the
    surfaces render, so the header cannot disagree with the page."""
    results = [score for profile in result.profiles.values()
               for score in profile.all_scores()]
    return {
        "parts_scored": len(result.profiles),
        "dimension_results": len(results),
        "executing": sum(1 for s in results if s.autonomy == gov.EXECUTES),
        "deferring": sum(1 for s in results if s.autonomy == gov.RECOMMENDS),
        "clusters_concentrated": len(result.report.concentrated()),
    }


def overview_payload(result, built):
    """The Overview surface's aggregates, computed by the LIBRARY.

    Every figure here comes from `interface.dashboard`, which is already tested
    and already carries the decisions that matter: which regions appear even
    when the map cannot draw them, that archetype groups keep lattice order
    rather than being sorted by size, that the work queue IS legitimately a
    ranking and the lattice is not. Recomputing any of that in the frontend
    would put a second copy of a judgment in a language none of these tests can
    reach.

    `dimension_series` carries floats, and that is correct rather than a lapse:
    it is a CHART SERIES and not a measure. The measures themselves are in
    `profiles`, exact. A caller wanting a figure to quote reads those.
    """
    parts, suppliers, grid = dash.incidence(result)
    exposure = built[view.EXPOSURE]
    return {
        "tiles": encode(dash.tiles(result)),
        "dimension_series": encode(dash.dimension_series(result)),
        "regions": encode(dash.regions(result)),
        "incidence": {"parts": list(parts), "suppliers": list(suppliers),
                      "grid": encode(grid),
                      "exposed_parts": len(dash.exposed_parts(result))},
        "coverage_counts": encode(dash.coverage_counts(exposure.coverage))
        if exposure.coverage else [],
        "group_sizes": encode(dash.group_sizes(exposure)),
        "field_sizes": encode(dash.field_sizes(built[view.FIND_OUT])),
        "cluster_sizes": encode(dash.cluster_sizes(result.report)),
        # ONE ROW PER COUNTRY, so a map can fill shapes without the frontend
        # learning which countries stand for which region. That mapping is a
        # DRAWING CONVENTION and not a claim about where a supplier is, and the
        # surface says so; keeping it in Python keeps the convention and its
        # caveat in the same place.
        "map_rows": [
            {"country": code, "name": dash.COUNTRY_NAME.get(code, code),
             "region": row.region, "region_label": row.label,
             "suppliers": row.suppliers, "parts": row.parts,
             "exposed_parts": row.exposed_parts}
            for row in dash.regions(result) for code in row.countries],
        # THE DISPLAY NAME FOR AN INTERNAL KEY, served rather than hardcoded in
        # the frontend. `south_asia` is the key a cluster is identified by and
        # must stay exactly that on the wire; "South Asia" is what a person
        # reads. A second copy of this map in TypeScript is how the two drift
        # until a region appears on one screen under two spellings, which is
        # what the interface does today.
        "region_labels": encode(dash.REGION_LABEL),
        # The verdict codes in plain words, from the renderer's own map. Served
        # rather than copied into the frontend, so the words a heading shows and
        # the words a sentence uses cannot drift into two vocabularies for one
        # fact.
        "verdict_labels": encode(VERDICT_PROSE),
    }


def score_payload(result, record):
    """One run, whole. Structure everywhere, prose only where it was rendered.

    The sentences in here came out of `render()` a moment ago and were never
    stored. Everything else is the library's own dataclasses encoded field for
    field, so a caller sees what the Streamlit surface sees and not a summary
    somebody chose for them.
    """
    built = surfaces(result)
    return {
        "run": dict(record, counts=_counts(result)),
        "overview": overview_payload(result, built),
        "verdicts": encode(result.verdicts),
        "profiles": {
            part: {score.dimension: encode(score)
                   for score in profile.all_scores()}
            for part, profile in result.profiles.items()},
        "surfaces": {
            "exposure": encode(built[view.EXPOSURE]),
            "what_to_check": encode(built[view.FIND_OUT]),
            "review": encode(built[view.CONFIRM]),
        },
        "clusters": encode(result.report.clusters),
        "unplaceable_parts": encode(result.report.unplaceable_parts),
        "extracts": encode(result.extracts),
        "dimensions": list(scoring.DIMENSIONS),
        # NULL WHEN NOBODY HAS SET ONE, and the interface says so rather than
        # rendering a band nobody owns. The system ships with every threshold
        # commented out on purpose: out of the box it can name the resourcing
        # trap and cannot say "long lead" until a named person states what long
        # means.
        "thresholds": encode(result.thresholds),
        # WHERE A COMPETITOR PUTS AN INDEX. Computed in `src/binding.py`, which
        # compares states and never magnitudes, so the interface can name what
        # is wrong with a part without the frontend inventing a ranking that no
        # Python test could reach. See that module for why blast radius and
        # resourcing days appear in `no_terminal_state` rather than binding.
        "binding": {part: encode(binding.summary(profile))
                    for part, profile in result.profiles.items()},
    }


# ------------------------------------------------------------------ score --

def _scored(data_dir, record):
    return score_payload(run(data_dir=data_dir), record)


@app.post("/api/score")
async def score(files: list[UploadFile] = None, dataset: str = Form(None)):
    """Score an uploaded set of CSVs, or a dataset this repository ships.

    An upload is written to a run directory and scored from there, so the bytes
    that produced an answer are still on disk when somebody asks how it was
    reached. Nothing is scored from memory and discarded.
    """
    files = [f for f in (files or []) if f.filename]
    if files:
        with tempfile.TemporaryDirectory() as staging:
            staging = Path(staging)
            for upload in files:
                name = Path(upload.filename).name
                (staging / name).write_bytes(await upload.read())
            missing = [name for name in REQUIRED_FILES
                       if not (staging / name).exists()]
            if missing:
                raise HTTPException(status_code=422, detail={
                    "error": "required files are missing from the upload",
                    "missing": missing,
                    "required": list(REQUIRED_FILES),
                    "optional": list(OPTIONAL_FILES)})
            record = runs.record_run(staging, dataset or "uploaded")
            return _scored(Path(record["data_dir"]), record)

    name = dataset or DEFAULT_DATASET
    if name not in BUILT_IN:
        raise HTTPException(status_code=404, detail={
            "error": f"no dataset named {name!r}",
            "available": sorted(BUILT_IN)})
    directory = BUILT_IN[name]
    if not (directory / "bom.csv").exists():
        raise HTTPException(status_code=404, detail={
            "error": f"the {name!r} dataset is not present in this deployment",
            "expected_at": str(directory)})
    record = runs.record_run(directory, name, copy_inputs=False)
    return _scored(directory, record)


@app.get("/api/run/{run_id}")
def get_run(run_id: str):
    record = runs.load_run(run_id)
    if record is None:
        raise HTTPException(status_code=404,
                            detail={"error": f"no run named {run_id!r}"})
    data_dir = Path(record["data_dir"])
    if not (data_dir / "bom.csv").exists():
        # STATED, NEVER SUBSTITUTED. Scoring a different directory because this
        # one is gone would answer a question nobody asked, under an id that
        # says it is answering another.
        raise HTTPException(status_code=410, detail={
            "error": "the inputs this run was scored from are no longer there, "
                     "and a run is its inputs",
            "expected_at": str(data_dir)})
    return _scored(data_dir, record)


@app.get("/api/runs")
def get_runs():
    return {"runs": runs.list_runs()}


# -------------------------------------------------------------- decisions --

class DecisionIn(BaseModel):
    run_id: str
    subject: str
    action: str
    decided_by: str
    reason_code: str = ""
    note: str = ""


@app.post("/api/decisions")
def post_decision(decision: DecisionIn):
    """Record one judgment, THROUGH `actions.apply` and never around it.

    Every refusal that module makes is a rule this product is built on: an
    anonymous decision is not a decision, a rejection needs a reason, "other"
    needs the note it promises, and the same person clicking the same button
    twice is one judgment arriving twice. Reimplementing any of them here would
    put a second copy of a rule in a place no existing test looks.

    The control is FOUND, never constructed. Its existence is the autonomy
    claim: a subject with no control on the Review surface is one this system
    does not offer a human the power to decide, and building a control here to
    satisfy a request would hand that power over at the transport layer.
    """
    record = runs.load_run(decision.run_id)
    if record is None:
        raise HTTPException(status_code=404, detail={
            "error": f"no run named {decision.run_id!r}"})

    review = surfaces(run(data_dir=Path(record["data_dir"])))[view.CONFIRM]
    control = next(
        (c for row in review.all_rows() for c in row.controls
         if c.subject == decision.subject and c.action == decision.action),
        None)
    if control is None:
        raise HTTPException(status_code=404, detail={
            "error": f"no {decision.action!r} control for "
                     f"{decision.subject!r} on this run",
            "subjects": sorted({c.subject for row in review.all_rows()
                                for c in row.controls})})

    log = store.load()
    try:
        event = actions.apply(
            log, control, decided_by=decision.decided_by,
            reason_code=decision.reason_code, note=decision.note,
            at=datetime.now(timezone.utc).isoformat())
    except ValueError as refused:
        # The refusal text IS the answer. Replacing it with a generic 400 would
        # throw away the one sentence that says what to do differently.
        raise HTTPException(status_code=409,
                            detail={"error": str(refused)}) from refused
    store.append(event)
    return {"decision": encode(event), "sentence": _render(event)}


@app.get("/api/decisions")
def get_decisions():
    """The log, with each sentence RENDERED NOW rather than read from the file.

    The file holds no prose, on purpose, so this is the only place a sentence
    for a stored decision can come from. A wording change therefore reaches
    every decision ever recorded, which is the property storing the prose would
    have destroyed.
    """
    log = store.load()
    return {"decisions": [dict(encode(event), sentence=_render(event))
                          for event in log],
            "reason_codes": list(gov.REASON_CODES)}


def _render(event):
    from ..governance.render import render
    return render(event)


@app.get("/api/assets/india-claimed.geojson")
def india_boundary():
    """India including the full claimed territory, served from the one copy.

    WHY IT IS SERVED RATHER THAN COPIED INTO THE FRONTEND. Natural Earth's `IND`
    polygon follows a different convention and stops around 35.5N, and that
    geometry ships inside the chart library where nothing can reach it, so the
    only way to draw India complete is to supply the shape. `assets/README.md`
    carries the source, the CC BY 4.0 licence and the derivation, and
    `tests/test_map_geometry.py` asserts the northern and eastern reach so a
    future resimplification cannot quietly clip a claimed region.

    A second copy under `web/public/` would be a second thing to keep in step
    with that test, and the test can only see one of them.
    """
    path = Path("assets/india-claimed.geojson")
    if not path.exists():
        raise HTTPException(status_code=404, detail={
            "error": "the India boundary asset is not in this deployment",
            "expected_at": str(path)})
    return FileResponse(path, media_type="application/geo+json")


@app.get("/api/health")
def health():
    """For the host's liveness check. Says which datasets it can actually see,
    because a container that is up and has no data is not healthy."""
    return {"status": "ok",
            "datasets": sorted(name for name, path in BUILT_IN.items()
                               if (path / "bom.csv").exists())}
