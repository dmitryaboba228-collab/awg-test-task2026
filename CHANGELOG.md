# Changelog

All notable changes to this project are documented in this file.

## [0.2.0] — 2026-09-16

### Added

- Clone-from-URL (`POST /repos`, `GET /repos`): https-only, no credentials,
  post-clone size limit, per-URL locking, one-time `.mailmap` prefetch on a
  blobless clone (ADR-01 addendum, ADR-02)
- Workspace/registry mode: `create_router`/`create_app` accept
  `workspace_path` alongside the existing `repo_path`; every read endpoint
  takes an optional `repo` query param; the registry rebuilds its listing
  from workspace directory contents, no database
- Author filter: `list_authors` now backed by `git shortlog` (mailmap-
  applied, stays small on a huge history); `author` query param on
  `/commits` and `/activity`, matched against the canonical mailmap email
- Activity trend now covers the whole history via `GitRepository.
  list_commit_dates` (dates only), not a 500-commit window
- UI: "Connect a repository" form, author filter, top-5 contribution share
  with an "Others" row, SVG weekly-activity chart, and a "How metrics are
  computed" panel explaining the ADR-03 limits
- `deploy/`: Dockerfile (installs a pre-built wheel, mirrors
  `examples/host-vendor`) and `app.py` (workspace mode host)
- `make package-verify` now mounts the wheel in both `repo_path` and
  `workspace` mode against a throwaway repo, not just an import check

## [0.1.0] — 2026-09-15

### Added

- Embeddable `gitpulse` package with `create_router`, `create_app`, `mount_static_ui`
- Local git adapter with mailmap, timeouts, and hook disable
- React UI for branches, commits, authors, contribution share, and weekly activity
- Fixture host, vendor-host example, contracts export, and privacy gate
- Orphan `docs/vault` DDD map and ADRs
