# The API container. The frontend is deployed separately, on Vercel.
#
# WHY A CONTAINER AT ALL. Streamlit Community Cloud sleeps an idle app, which
# has already meant a dead link in front of somebody who mattered. A container
# on a host that stays awake is the fix, and it is the backend that has to stay
# awake: the frontend is static and Vercel does not sleep it.
FROM python:3.12-slim

WORKDIR /app

# Dependencies first, so a code change does not reinstall pandas.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY config/ ./config/
COPY demo/ ./demo/
COPY evals/ ./evals/
COPY assets/ ./assets/

# The demo dataset is COPIED IN, on purpose. A cold container cannot generate
# data during its first request, so without it the first caller gets an error
# rather than a page. `evals/` rides along because it is the frozen set the
# regression tests score against and it is small.
#
# `assets/` IS NOT DECORATION. It holds the vendored India boundary, and
# `/api/assets/india-claimed.geojson` reads it from the working directory at
# request time. Left out, that endpoint 404s on every request the map makes and
# the page falls back to plotly's built-in geometry, which follows a different
# territorial convention and draws India stopping around 35.5N. The frontend
# says so rather than drawing it silently, which is the point of `RegionMap`'s
# failed state -- but a deployment that shows that state permanently is one
# nobody should have shipped. See `assets/README.md`.
#
# `data/` and `truth/` are NOT copied. They are gitignored and regenerated from
# a documented seed, and a container carrying an unversioned copy of them would
# be scoring something nobody can reproduce.

ENV SEA_RUNS_DIR=/data/runs \
    SEA_DECISIONS_DIR=/data/decisions \
    PORT=8000

# Both are written at request time and both must OUTLIVE A DEPLOY. A decision
# log that resets when the container restarts is the exact defect
# `governance/store.py` was written to close, one layer out: mount a volume at
# /data on whichever host this runs on.
VOLUME ["/data"]

EXPOSE 8000
CMD ["sh", "-c", "uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT}"]
