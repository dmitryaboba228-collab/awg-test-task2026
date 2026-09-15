"""Production host: installs gitpulse from a wheel, clones public repos on demand.

Mirrors `examples/host-vendor/app.py` — the host installs a pre-built wheel,
it does not build the package itself. Unlike the vendor example (single
fixed `repo_path`), this host runs in workspace/registry mode (ADR-02) so
the UI's "Connect a repository" form can clone arbitrary public URLs
without a restart. Set `GITPULSE_REPO_PATH` as well to also serve a fixed
repository alongside the registry; both parameters accept coexisting.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI

from gitpulse.fastapi_app import create_router, mount_static_ui

WORKSPACE = Path(os.environ.get('GITPULSE_WORKSPACE', '/data/workspace'))
REPO_PATH_ENV = os.environ.get('GITPULSE_REPO_PATH')

app = FastAPI(title='AWG GitPulse')
app.include_router(
    create_router(
        mount_path='/git',
        workspace_path=WORKSPACE,
        repo_path=Path(REPO_PATH_ENV) if REPO_PATH_ENV else None,
    ),
    prefix='/git',
)
mount_static_ui(app, mount_path='/git')


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok', 'host': 'deploy'}
