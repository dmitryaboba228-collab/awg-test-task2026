# Server runbook

Everything here is pre-built and tested locally (`docker compose` wiring,
Caddyfile, reverse proxy, HTTP→HTTPS redirect). Once SSH access to the
target server works, deploying is just:

```bash
# on the server, after cloning/copying this repository
git checkout chore/deploy   # or whichever branch/tag is being deployed

export GITPULSE_DOMAIN=<public hostname>
# no owned domain yet: use a sslip.io address for the server's own IP,
# e.g. GITPULSE_DOMAIN=203-0-113-42.sslip.io for IP 203.0.113.42 —
# Let's Encrypt issues a real certificate for it, no DNS setup needed.

deploy/run.sh
```

`run.sh` builds the wheel (`make package`), brings up `gitpulse` + `caddy`
via `deploy/docker-compose.yml`, and polls `https://$GITPULSE_DOMAIN/health`
until it answers (Caddy needs a few seconds to get the certificate on first
start).

## What's running

- **`gitpulse`** — the app from `deploy/Dockerfile` (installs the wheel
  built by `make package`), not published on the host directly.
- **`caddy`** — the only thing listening on 80/443. Redirects HTTP to
  HTTPS, terminates TLS with a certificate it obtains and renews itself,
  reverse-proxies everything to `gitpulse:8000`.

Both `gitpulse-workspace` (cloned repos) and `caddy-data`/`caddy-config`
(the certificate) are named Docker volumes, so a `docker compose ... up -d`
after a reboot does not lose either.

## After it's up

1. Confirm from *outside* the server too, not just `curl localhost` on the
   box itself — `curl https://$GITPULSE_DOMAIN/health` from another machine.
2. Open `https://$GITPULSE_DOMAIN/git/`, connect a large public repository
   through the UI form, confirm it shows up with real data.
3. Put the URL in the root `README.md`'s Deployment section (replacing the
   placeholder) and commit that on its own.
4. Once every Definition of Done item is actually true, run
   `make timelog-dod` and commit `TIMELOG.md`.

## If something doesn't come up

```bash
docker compose -f deploy/docker-compose.yml logs --tail 50
docker compose -f deploy/docker-compose.yml ps
```

A `tls.obtain` error in the Caddy logs almost always means `GITPULSE_DOMAIN`
doesn't actually resolve to this server yet, or port 80 isn't reachable from
the internet (Let's Encrypt's HTTP-01 challenge needs it) — check the
firewall/security group before anything else.
