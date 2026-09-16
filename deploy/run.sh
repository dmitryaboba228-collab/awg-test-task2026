#!/usr/bin/env bash
# One-shot deploy: build the wheel, bring up gitpulse + Caddy, wait for
# the public HTTPS endpoint to answer.
#
# Run from the repository root, on the target server:
#
#   GITPULSE_DOMAIN=1-2-3-4.sslip.io deploy/run.sh
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

: "${GITPULSE_DOMAIN:?set GITPULSE_DOMAIN, e.g. 1-2-3-4.sslip.io (your server's own IP)}"
export GITPULSE_DOMAIN

echo "==> building wheel (make package)"
make package

echo "==> starting gitpulse + caddy (docker compose)"
docker compose -f deploy/docker-compose.yml up -d --build

echo "==> waiting for https://${GITPULSE_DOMAIN}/health (Caddy needs a moment to get a certificate)"
for _ in $(seq 1 30); do
  if curl -fsS "https://${GITPULSE_DOMAIN}/health" >/dev/null 2>&1; then
    echo "==> up: https://${GITPULSE_DOMAIN}/git/"
    exit 0
  fi
  sleep 5
done

echo "==> not answering yet after 150s — check logs:" >&2
echo "    docker compose -f deploy/docker-compose.yml logs --tail 50" >&2
exit 1
