"""API tests for `POST /repos` and `GET /repos` (ADR-02 workspace mode)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gitpulse.fastapi_app import create_app
from gitpulse.git import registry as registry_mod
from gitpulse.git.clone import validate_url


@pytest.fixture()
def workspace_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, sample_repo: Path
) -> TestClient:
    workspace = tmp_path / 'workspace'

    def fake_clone(url: str, ws: Path, *, max_bytes: int = 0) -> Path:
        validate_url(url)
        target = ws / 'demo-clone'
        if not target.exists():
            subprocess.run(
                ['git', 'clone', '--bare', str(sample_repo), str(target)],
                check=True,
                capture_output=True,
            )
        return target

    monkeypatch.setattr(registry_mod, 'clone', fake_clone)
    app = create_app(mount_path='/git', workspace_path=workspace, mount_ui=False)
    return TestClient(app)


def test_repos_empty_by_default(workspace_client: TestClient) -> None:
    response = workspace_client.get('/git/api/v1/repos')
    assert response.status_code == 200
    assert response.json() == []


def test_add_repo_then_list_and_query(workspace_client: TestClient) -> None:
    created = workspace_client.post(
        '/git/api/v1/repos', json={'url': 'https://example.com/octo/demo.git'}
    )
    assert created.status_code == 201
    repo_id = created.json()['id']
    assert created.json()['url'] == 'https://example.com/octo/demo.git'

    listed = workspace_client.get('/git/api/v1/repos')
    assert listed.status_code == 200
    assert [row['id'] for row in listed.json()] == [repo_id]

    summary = workspace_client.get('/git/api/v1/summary', params={'repo': repo_id})
    assert summary.status_code == 200
    assert summary.json()['commit_count'] == 2


def test_add_repo_bad_url_returns_422(workspace_client: TestClient) -> None:
    response = workspace_client.post('/git/api/v1/repos', json={'url': 'ext::sh -c pwn'})
    assert response.status_code == 422


def test_query_missing_repo_param_is_422(workspace_client: TestClient) -> None:
    response = workspace_client.get('/git/api/v1/summary')
    assert response.status_code == 422


def test_query_unknown_repo_is_404(workspace_client: TestClient) -> None:
    response = workspace_client.get('/git/api/v1/summary', params={'repo': 'nope'})
    assert response.status_code == 404


def test_repo_path_mode_ignores_repo_param(client: TestClient) -> None:
    """`client` fixture (conftest) runs in single repo_path mode."""

    response = client.get('/git/api/v1/repos')
    assert response.status_code == 200
    assert response.json() == []

    summary = client.get('/git/api/v1/summary', params={'repo': 'anything'})
    assert summary.status_code == 200
