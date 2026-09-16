"""Pytest fixtures."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gitpulse.fastapi_app import create_app


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ['git', '-c', 'core.hooksPath=/dev/null', '-C', str(repo), *args],
        check=True,
        capture_output=True,
    )


@pytest.fixture()
def sample_repo(tmp_path: Path) -> Path:
    repo = tmp_path / 'repo'
    repo.mkdir()
    _git(repo, 'init', '-b', 'main')
    _git(repo, 'config', 'user.name', 'Ada Lovelace')
    _git(repo, 'config', 'user.email', 'ada@example.com')
    (repo / 'README.md').write_text('one\n', encoding='utf-8')
    _git(repo, 'add', 'README.md')
    _git(repo, 'commit', '-m', 'feat: initial')
    _git(repo, 'config', 'user.name', 'Ada L.')
    _git(repo, 'config', 'user.email', 'ada@example.org')
    (repo / 'README.md').write_text('one\ntwo\n', encoding='utf-8')
    _git(repo, 'add', 'README.md')
    _git(repo, 'commit', '-m', 'docs: expand readme')
    (repo / '.mailmap').write_text(
        'Ada Lovelace <ada@example.com> Ada L. <ada@example.org>\n',
        encoding='utf-8',
    )
    _git(repo, 'checkout', '-b', 'feat/sample')
    (repo / 'note.txt').write_text('note\n', encoding='utf-8')
    _git(repo, 'add', 'note.txt')
    _git(repo, 'commit', '-m', 'feat: note')
    _git(repo, 'checkout', 'main')
    return repo


@pytest.fixture()
def client(sample_repo: Path) -> TestClient:
    app = create_app(mount_path='/git', repo_path=sample_repo, mount_ui=False)
    return TestClient(app)


@pytest.fixture()
def two_author_repo(tmp_path: Path) -> Path:
    """Repo with two distinct canonical authors, one behind a mailmap alias.

    Also has an author (`nomada`) whose email contains the other author's
    email as a substring, to catch unbracketed `--author` matching.
    """

    repo = tmp_path / 'two-author-repo'
    repo.mkdir()
    _git(repo, 'init', '-b', 'main')
    _git(repo, 'config', 'user.name', 'Ada Lovelace')
    _git(repo, 'config', 'user.email', 'ada@example.com')
    (repo / 'README.md').write_text('one\n', encoding='utf-8')
    _git(repo, 'add', 'README.md')
    _git(repo, 'commit', '-m', 'feat: one')
    _git(repo, 'config', 'user.name', 'Ada L.')
    _git(repo, 'config', 'user.email', 'ada@example.org')
    (repo / 'README.md').write_text('one\ntwo\n', encoding='utf-8')
    (repo / '.mailmap').write_text(
        'Ada Lovelace <ada@example.com> Ada L. <ada@example.org>\n',
        encoding='utf-8',
    )
    _git(repo, 'add', 'README.md', '.mailmap')
    _git(repo, 'commit', '-m', 'docs: expand readme')
    _git(repo, 'config', 'user.name', 'Bob B.')
    _git(repo, 'config', 'user.email', 'bob@example.com')
    (repo / 'bob.txt').write_text('bob\n', encoding='utf-8')
    _git(repo, 'add', 'bob.txt')
    _git(repo, 'commit', '-m', 'feat: bob joins')
    _git(repo, 'config', 'user.name', 'Nomada Smith')
    _git(repo, 'config', 'user.email', 'nomada@example.com')
    (repo / 'nomada.txt').write_text('nomada\n', encoding='utf-8')
    _git(repo, 'add', 'nomada.txt')
    _git(repo, 'commit', '-m', 'feat: nomada joins')
    return repo


@pytest.fixture()
def two_author_client(two_author_repo: Path) -> TestClient:
    app = create_app(mount_path='/git', repo_path=two_author_repo, mount_ui=False)
    return TestClient(app)
