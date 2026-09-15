# AWG GitPulse — test task (2026)

Hiring exercise for an AI-engineering teammate. The repository ships a **reference
satellite library**: a Python package that mounts into a FastAPI host, ships its
own React UI, and surfaces local git metadata through a clean module boundary.

You will fork this pattern into your own project, connect arbitrary public
repositories, and extend analytics. The reference is intentionally incomplete —
it demonstrates packaging, mounting, and process, not the full product.

## What you get

- Python package `awg-gitpulse-test` (import name `gitpulse`)
- Public host API: `create_router`, `create_app`, `mount_static_ui`
- React + TypeScript + Vite UI packaged into the wheel
- Local git adapter (argv-only, timeouts, mailmap, no hooks)
- Branches: `dev` (integration), `main` (release), `docs/vault` (DDD vault)
- Cursor rules, PR template, `AGENTS.md`, `TIMELOG.md`

## What you must build

1. Move into your own repository (keep the satellite-library shape).
2. Accept any public git URL, clone it safely, and analyze it.
3. Add an action filter by user.
4. Ship an activity / contribution dashboard (share per author, trends).
5. Deploy somewhere public and connect a large real repository.
6. Track time in `TIMELOG.md` (`build_started`, `dod_submitted`).

If you have hosting — use it. If not — write [@mazazyrikbeats](https://t.me/mazazyrikbeats).

## Definition of Done

- Service is reachable on the public internet
- A large public repository is connected and visible in the UI
- User filter works
- Contribution / activity metrics are visible and explained
- PRs followed gitflow into `dev`, vault decisions recorded where needed
- `TIMELOG.md` contains start and DoD timestamps

## Evaluation criteria

| Area | What we look for |
|------|------------------|
| Packaging | Wheel installs; host mounts the module under a prefix |
| Process | Conventional Commits, PR → `dev`, vault/ADR discipline |
| Git engineering | Safety (no shell, timeouts, hook disable), mailmap, caching |
| Product sense | Clear UX, honest metrics, documented limits |
| Agent harness | Useful `AGENTS.md` / rules; human vs agent split respected |
| Delivery | Live URL + large repo demo |

## Human vs agent

Read both:

- **This README** — assignment, DoD, evaluation, local runbook (human)
- **[AGENTS.md](AGENTS.md)** — implementation constraints for coding agents

Decisions a human must own and defend: module boundaries, cache strategy, ADR
updates, prioritization, and final acceptance of the deployed result.

## Local quickstart (reference)

```bash
# Node 20+ and pnpm via corepack; Poetry 2.x
export PATH="$HOME/.local/bin:$PATH"
make install
make ci-check
poetry run uvicorn fixtures.host.app:app --reload
# UI  http://127.0.0.1:8000/git/
# API http://127.0.0.1:8000/git/api/v1/health
```

Package release:

```bash
make package
# dist/*.whl + SHA256SUMS
# see examples/host-vendor for vendoring the wheel into a host app
```

## Deployment

`deploy/` holds the production host: `deploy/app.py` mounts `gitpulse` in
workspace mode (ADR-02), so the UI's "Connect a repository" form can clone
any public `https://` URL at runtime — no restart, no fixed local checkout.
`deploy/Dockerfile` installs a pre-built wheel; it does not build the
package, mirroring `examples/host-vendor`.

**With a public HTTPS endpoint** (the real deployment target — see
[deploy/README.md](deploy/README.md) for the full runbook):

```bash
export GITPULSE_DOMAIN=<public hostname>   # e.g. a sslip.io address for
                                            # the server's own IP if there
                                            # is no owned domain yet
deploy/run.sh
```

This brings up `gitpulse` behind `caddy` (`deploy/docker-compose.yml`),
which terminates TLS with a certificate it obtains and renews itself and
reverse-proxies everything else to the app — no manual certbot step.
Verified locally end to end (build, both containers healthy, UI and API
reachable through the proxy, HTTP redirected to HTTPS) using Caddy's
internal certificate authority in place of a real one, since issuing a real
Let's Encrypt certificate needs the domain to actually resolve to a
publicly reachable server.

**Single container, no TLS** (quick local/manual testing):

```bash
make package                                          # dist/*.whl
docker build -f deploy/Dockerfile -t gitpulse .
docker run -p 8000:8000 -v gitpulse-workspace:/data/workspace gitpulse
# UI  http://127.0.0.1:8000/git/
# API http://127.0.0.1:8000/git/api/v1/health
```

`make package-verify` installs the wheel into an isolated venv and mounts it
in both `repo_path` and `workspace` mode against a throwaway repo — run it
before building either image.

Without Docker, `deploy/app.py` runs the same way as
`examples/host-vendor/app.py`: `pip install dist/*.whl`, then
`GITPULSE_WORKSPACE=/path/to/workspace uvicorn app:app --port 8000` from
inside `deploy/`.

Environment variables:

| Variable | Meaning | Default |
|----------|---------|---------|
| `GITPULSE_WORKSPACE` | Directory clones live in (workspace/registry mode) | `/data/workspace` |
| `GITPULSE_REPO_PATH` | Also serve one fixed local repository alongside the registry | unset |
| `PORT` | Port `uvicorn` binds to | `8000` |

**Live deployment:** _not yet public — hosting, credentials, and the deploy
target are [@mazazyrikbeats](https://t.me/mazazyrikbeats)'s / the
maintainer's call, per [AGENTS.md](AGENTS.md#human-responsibilities-do-not-silently-take-over). URL goes here once deployed._

**Limitations** (see `docs/vault/adr/ADR-01-strategy.md` and `ADR-03` for the
full reasoning):

- Only public `https://` repositories can be connected — no credentials are
  ever accepted or forwarded, so private and non-existent repos fail fast
  instead of hanging.
- Disk grows with every connected repository: each clone is capped at 2 GiB
  by default, but nothing currently reclaims space, and many mid-sized repos
  can still fill the volume.
- Cloning is blobless (`--filter=blob:none`), so the first request against a
  freshly connected large repository is slower while git lazily fetches the
  objects that request needs (a `.mailmap`, if present, is prefetched once
  right after cloning).
- Contribution share counts non-merge commits per author, not lines changed
  — a one-line fix and a thousand-line refactor count the same.
- The weekly activity trend covers the whole history, not a recent window;
  a repository whose non-merge commit dates alone exceed the git
  output-size limit will report a clear error instead of a silently
  truncated trend.

## Gitflow

- Feature branches from `origin/dev`
- Pull requests target `dev`
- `docs/vault` is an orphan branch edited only from its worktree — never merge it
- `main` receives release merges and version tags (`v0.1.0`, …)

## TIMELOG

Agents must append ISO-8601 UTC rows when a build starts and when DoD is submitted:

```bash
make timelog-start
make timelog-dod
```
