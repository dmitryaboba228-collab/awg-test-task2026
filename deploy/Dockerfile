# AWG GitPulse deploy image.
#
# This image installs a pre-built wheel — it does not build the package.
# Run `make package` first (builds the UI, packages it into the wheel, and
# writes dist/*.whl), then build from the repository root so `dist/` is in
# the build context:
#
#   make package
#   docker build -f deploy/Dockerfile -t gitpulse .
#   docker run -p 8000:8000 -v gitpulse-workspace:/data/workspace gitpulse
#
FROM python:3.11-slim

# git: the gitpulse git adapter shells out to it (clone, log, shortlog, …).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY dist/*.whl /tmp/dist/
RUN pip install --no-cache-dir /tmp/dist/*.whl && rm -rf /tmp/dist

COPY deploy/app.py /app/app.py

# Clones land here (ADR-02). Mount a volume in production so a connected
# repository survives a restart instead of being re-cloned.
ENV GITPULSE_WORKSPACE=/data/workspace
RUN mkdir -p /data/workspace
VOLUME ["/data/workspace"]

EXPOSE 8000
ENV PORT=8000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
