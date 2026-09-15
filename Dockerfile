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

# The demo dataset is COPIED IN, on purpose. A cold container cannot generate
# data during its first request, so without it the first caller gets an error
# rather than a page. `evals/` rides along because it is the frozen set the
# regression tests score against and it is small.
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
