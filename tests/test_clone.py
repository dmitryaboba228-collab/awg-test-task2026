"""Tests for the clone-from-URL safety rules (ADR-01 addendum)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from gitpulse.git import clone as clone_mod
from gitpulse.git.clone import (
    CloneTooLargeError,
    InvalidRepoUrlError,
    clone,
    validate_url,
)
from gitpulse.git.errors import GitCommandError


@pytest.mark.parametrize(
    'url',
    [
        'ext::sh -c touch%20/tmp/pwned',
        'file:///etc/passwd',
        'ssh://git@example.com/repo.git',
        '',
        '   ',
        'https://',
    ],
)
def test_validate_url_rejects_unsafe_input(url: str) -> None:
    with pytest.raises(InvalidRepoUrlError):
        validate_url(url)


def test_validate_url_rejects_embedded_credentials() -> None:
    with pytest.raises(InvalidRepoUrlError):
        validate_url('https://user:pass@example.com/repo.git')


def test_validate_url_accepts_plain_https() -> None:
    assert validate_url(' https://example.com/repo.git ') == 'https://example.com/repo.git'


def test_clone_argv_disables_prompts_and_credentials(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}

    def fake_run(cmd, *, check, capture_output, timeout, env, shell):  # noqa: ANN001
        if 'clone' in cmd:
            captured['cmd'] = cmd
            captured['env'] = env
            Path(cmd[-1]).mkdir(parents=True)
        return subprocess.CompletedProcess(cmd, 0, b'', b'')

    monkeypatch.setattr(clone_mod.subprocess, 'run', fake_run)
    clone('https://example.com/octo/demo.git', tmp_path / 'workspace')

    cmd = captured['cmd']
    assert cmd[0] == 'git'
    assert 'credential.helper=' in cmd
    assert 'protocol.allow=never' in cmd
    assert 'protocol.https.allow=always' in cmd
    assert '--bare' in cmd
    assert '--filter=blob:none' in cmd
    assert cmd[-2] == 'https://example.com/octo/demo.git'
    env = captured['env']
    assert env['GIT_TERMINAL_PROMPT'] == '0'


def test_clone_timeout_raises_git_command_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_run(cmd, *, check, capture_output, timeout, env, shell):  # noqa: ANN001
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(clone_mod.subprocess, 'run', fake_run)
    with pytest.raises(GitCommandError):
        clone('https://example.com/octo/demo.git', tmp_path / 'workspace', timeout=1)


def test_clone_failure_removes_partial_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def fake_run(cmd, *, check, capture_output, timeout, env, shell):  # noqa: ANN001
        target = Path(cmd[-1])
        target.mkdir(parents=True)
        return subprocess.CompletedProcess(cmd, 128, b'', b'fatal: repository not found')

    monkeypatch.setattr(clone_mod.subprocess, 'run', fake_run)
    workspace = tmp_path / 'workspace'
    with pytest.raises(GitCommandError):
        clone('https://example.com/octo/missing.git', workspace)

    target = workspace / clone_mod._repo_dir_name('https://example.com/octo/missing.git')
    assert not target.exists()


def test_clone_over_size_limit_is_removed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_run(cmd, *, check, capture_output, timeout, env, shell):  # noqa: ANN001
        target = Path(cmd[-1])
        target.mkdir(parents=True)
        (target / 'objects.pack').write_bytes(b'x' * 1024)
        return subprocess.CompletedProcess(cmd, 0, b'', b'')

    monkeypatch.setattr(clone_mod.subprocess, 'run', fake_run)
    workspace = tmp_path / 'workspace'
    with pytest.raises(CloneTooLargeError):
        clone('https://example.com/octo/demo.git', workspace, max_bytes=100)

    target = workspace / clone_mod._repo_dir_name('https://example.com/octo/demo.git')
    assert not target.exists()


def test_clone_reuses_existing_target(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls = 0

    def fake_run(cmd, *, check, capture_output, timeout, env, shell):  # noqa: ANN001
        if 'clone' in cmd:
            nonlocal calls
            calls += 1
            Path(cmd[-1]).mkdir(parents=True)
        return subprocess.CompletedProcess(cmd, 0, b'', b'')

    monkeypatch.setattr(clone_mod.subprocess, 'run', fake_run)
    workspace = tmp_path / 'workspace'
    first = clone('https://example.com/octo/demo.git', workspace)
    second = clone('https://example.com/octo/demo.git', workspace)
    assert first == second
    assert calls == 1
