"""Registry of cloned repositories backed by a workspace directory.

No database: the source URL is written into a marker file inside each clone
directory, so the registry rebuilds its listing from disk contents after a
restart (ADR-02).
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from pathlib import Path

from gitpulse.core.models import RepoInfo
from gitpulse.git.clone import DEFAULT_MAX_CLONE_BYTES, clone
from gitpulse.git.errors import GitPulseError
from gitpulse.git.repository import GitRepository, get_repository

_SOURCE_MARKER = '.gitpulse-source'


class UnknownRepoError(GitPulseError):
    """No repository is registered under this id."""


class RepoRegistry:
    """Clones public repositories into a workspace and serves them by id."""

    def __init__(self, workspace: Path | str) -> None:
        self.workspace = Path(workspace).expanduser().resolve()
        self._lock = threading.Lock()
        self._repos: dict[str, Path] = {}
        self._load_existing()

    def _load_existing(self) -> None:
        if not self.workspace.exists():
            return
        for entry in sorted(self.workspace.iterdir()):
            if entry.is_dir() and (entry / _SOURCE_MARKER).exists():
                self._repos[entry.name] = entry

    def add(self, url: str, *, max_bytes: int = DEFAULT_MAX_CLONE_BYTES) -> RepoInfo:
        """Clone `url` (or reuse the existing clone) and register it."""

        target = clone(url, self.workspace, max_bytes=max_bytes)
        marker = target / _SOURCE_MARKER
        if not marker.exists():
            marker.write_text(url.strip() + '\n', encoding='utf-8')
        with self._lock:
            self._repos[target.name] = target
        return self._info(target.name, target)

    def get(self, repo_id: str) -> GitRepository:
        path = self._repos.get(repo_id)
        if path is None or not path.exists():
            raise UnknownRepoError(f'unknown repo: {repo_id}')
        return get_repository(str(path))

    def list(self) -> list[RepoInfo]:
        return [self._info(repo_id, path) for repo_id, path in sorted(self._repos.items())]

    def _info(self, repo_id: str, path: Path) -> RepoInfo:
        marker = path / _SOURCE_MARKER
        url = marker.read_text(encoding='utf-8').strip() if marker.exists() else ''
        cloned_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        return RepoInfo(id=repo_id, url=url, path=str(path), cloned_at=cloned_at)
