# For a host that reads a Procfile (Railway, Render, Heroku-shaped). The
# Dockerfile is the fuller statement; this exists so a buildpack deploy works
# without one. $PORT is supplied by the host and is not ours to choose.
web: uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
