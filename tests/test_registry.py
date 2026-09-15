"""Tests for the workspace repo registry (ADR-02)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from gitpulse.git import registry as registry_mod
from gitpulse.git.registry import RepoRegistry, UnknownRepoError


def _bare_clone_locally(source: Path, target: Path) -> None:
    subprocess.run(
        ['git', 'clone', '--bare', str(source), str(target)],
        check=True,
        capture_output=True,
    )


def test_add_registers_and_persists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, sample_repo: Path
) -> None:
    workspace = tmp_path / 'workspace'

    def fake_clone(url: str, ws: Path, *, max_bytes: int = 0) -> Path:
        target = ws / 'demo-clone'
        _bare_clone_locally(sample_repo, target)
        return target

    monkeypatch.setattr(registry_mod, 'clone', fake_clone)
    registry = RepoRegistry(workspace)
    info = registry.add('https://example.com/octo/demo.git')

    assert info.id == 'demo-clone'
    assert info.url == 'https://example.com/octo/demo.git'
    marker = workspace / 'demo-clone' / '.gitpulse-source'
    assert marker.read_text(encoding='utf-8').strip() == 'https://example.com/octo/demo.git'

    repo = registry.get('demo-clone')
    assert repo.summary().commit_count == 2
    assert [row.id for row in registry.list()] == ['demo-clone']


def test_unknown_repo_raises(tmp_path: Path) -> None:
    registry = RepoRegistry(tmp_path / 'workspace')
    with pytest.raises(UnknownRepoError):
        registry.get('nope')


def test_registry_restores_from_disk(tmp_path: Path, sample_repo: Path) -> None:
    workspace = tmp_path / 'workspace'
    target = workspace / 'demo-clone'
    _bare_clone_locally(sample_repo, target)
    (target / '.gitpulse-source').write_text(
        'https://example.com/octo/demo.git\n', encoding='utf-8'
    )

    registry = RepoRegistry(workspace)
    listed = registry.list()
    assert len(listed) == 1
    assert listed[0].id == 'demo-clone'
    assert listed[0].url == 'https://example.com/octo/demo.git'


def test_missing_workspace_yields_empty_list(tmp_path: Path) -> None:
    registry = RepoRegistry(tmp_path / 'does-not-exist')
    assert registry.list() == []
