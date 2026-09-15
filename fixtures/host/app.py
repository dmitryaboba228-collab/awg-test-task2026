"""Minimal host application mounting AWG GitPulse under `/git`."""

from __future__ import annotations

import os
from pathlib import Path

from gitpulse.fastapi_app import create_app

ROOT = Path(__file__).resolve().parents[2]
REPO_PATH_ENV = os.environ.get('GITPULSE_REPO_PATH')
WORKSPACE_ENV = os.environ.get('GITPULSE_WORKSPACE')


def build_host_app():
    workspace_path = Path(WORKSPACE_ENV) if WORKSPACE_ENV else None
    if REPO_PATH_ENV:
        repo_path: Path | None = Path(REPO_PATH_ENV)
    elif workspace_path is None:
        repo_path = ROOT
    else:
        repo_path = None
    app = create_app(
        mount_path='/git',
        repo_path=repo_path,
        workspace_path=workspace_path,
        mount_ui=True,
    )

    @app.get('/health')
    def host_health() -> dict[str, str]:
        return {'status': 'ok', 'host': 'fixture'}

    return app


app = build_host_app()
