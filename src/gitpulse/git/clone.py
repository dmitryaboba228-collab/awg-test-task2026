"""Safe clone of public repositories over https.

Implements the ADR-01 clone-limits addendum: no credential prompts or
helpers, https-only transport, rejection of URLs carrying credentials, a
post-clone size limit, and one clone per URL at a time.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import threading
from pathlib import Path
from urllib.parse import urlparse

from gitpulse.git.errors import GitCommandError, GitPulseError

CLONE_TIMEOUT_SEC = 120
DEFAULT_MAX_CLONE_BYTES = 2 * 1024**3  # 2 GiB, per ADR-01 addendum (to confirm)
_ALLOWED_SCHEMES = frozenset({'https'})

_locks_guard = threading.Lock()
_url_locks: dict[str, threading.Lock] = {}


class InvalidRepoUrlError(GitPulseError):
    """Repository URL is rejected before git is invoked."""


class CloneTooLargeError(GitPulseError):
    """Clone exceeded the size limit and was removed from disk."""


def validate_url(url: str) -> str:
    """Return the url if it is a safe https URL without embedded credentials."""

    text = url.strip()
    if not text:
        raise InvalidRepoUrlError('url is empty')
    parsed = urlparse(text)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise InvalidRepoUrlError(f'unsupported scheme: {parsed.scheme or "none"}')
    if not parsed.netloc:
        raise InvalidRepoUrlError('url has no host')
    if parsed.username or parsed.password:
        raise InvalidRepoUrlError('url must not contain credentials')
    return text


def clone(
    url: str,
    workspace: Path,
    *,
    timeout: float = CLONE_TIMEOUT_SEC,
    max_bytes: int = DEFAULT_MAX_CLONE_BYTES,
) -> Path:
    """Clone a public repository as a bare mirror inside the workspace.

    Concurrent calls for the same url are serialized so only one clone runs;
    the second caller gets the already-cloned directory once the first
    finishes.
    """

    safe_url = validate_url(url)
    target = workspace / _repo_dir_name(safe_url)
    with _url_lock(safe_url):
        if target.exists():
            return target
        workspace.mkdir(parents=True, exist_ok=True)
        cmd = [
            'git',
            '-c',
            'core.hooksPath=/dev/null',
            '-c',
            'credential.helper=',
            '-c',
            'protocol.allow=never',
            '-c',
            'protocol.https.allow=always',
            'clone',
            '--bare',
            '--filter=blob:none',
            safe_url,
            str(target),
        ]
        completed = _run(cmd, timeout=timeout)
        if completed.returncode != 0:
            shutil.rmtree(target, ignore_errors=True)
            err = completed.stderr.decode('utf-8', errors='replace').strip()
            raise GitCommandError(err or f'clone failed ({completed.returncode})')
        size = _dir_size(target)
        if size > max_bytes:
            shutil.rmtree(target, ignore_errors=True)
            raise CloneTooLargeError(f'clone exceeded {max_bytes} bytes ({size} bytes), removed')
        _prefetch_mailmap(target, timeout=timeout)
        return target


def _prefetch_mailmap(target: Path, *, timeout: float) -> None:
    """Force the `.mailmap` blob to download once, right after cloning.

    The clone uses `--filter=blob:none`, so blob content is fetched lazily
    on first read. Without this, the first mailmap-aware query (list_authors,
    list_commits) would pay that network cost mid-request. A missing
    `.mailmap` file is not an error — the command is best-effort.
    """

    cmd = [
        'git',
        '-c',
        'credential.helper=',
        '-c',
        'protocol.allow=never',
        '-c',
        'protocol.https.allow=always',
        '-C',
        str(target),
        'cat-file',
        '-e',
        'HEAD:.mailmap',
    ]
    _run(cmd, timeout=timeout)


def _url_lock(url: str) -> threading.Lock:
    with _locks_guard:
        lock = _url_locks.get(url)
        if lock is None:
            lock = threading.Lock()
            _url_locks[url] = lock
        return lock


def _dir_size(path: Path) -> int:
    total = 0
    for entry in path.rglob('*'):
        if entry.is_file() and not entry.is_symlink():
            total += entry.stat().st_size
    return total


def _clone_env() -> dict[str, str]:
    return {
        **os.environ,
        'GIT_TERMINAL_PROMPT': '0',
        'LC_ALL': 'C.UTF-8',
        'LANG': 'C.UTF-8',
    }


def _run(cmd: list[str], *, timeout: float) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            timeout=timeout,
            env=_clone_env(),
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitCommandError(f'clone timed out after {timeout}s') from exc


def _repo_dir_name(url: str) -> str:
    digest = hashlib.sha256(url.encode('utf-8')).hexdigest()[:16]
    name = url.rstrip('/').rsplit('/', 1)[-1].removesuffix('.git')
    safe = ''.join(ch for ch in name if ch.isalnum() or ch in '-_') or 'repo'
    return f'{safe}-{digest}'
