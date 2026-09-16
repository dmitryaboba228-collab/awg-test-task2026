"""Read-only queries against a local git repository."""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from pathlib import Path

from gitpulse.core.models import Author, BranchRef, Commit, RepoSummary
from gitpulse.git import resolve_repo, run_git
from gitpulse.git.errors import UnknownAuthorError, UnknownRefError


def _parse_iso(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    return datetime.fromisoformat(text)


class GitRepository:
    """Facade over local git metadata used by the FastAPI layer."""

    def __init__(self, path: Path | str) -> None:
        self.path = resolve_repo(Path(path))

    def _run(self, args: list[str], *, timeout: float = 30) -> str:
        return run_git(self.path, args, timeout=timeout)

    def list_branches(self) -> list[BranchRef]:
        fmt = '%(refname:short)\t%(objectname)\t%(committerdate:iso-strict)\t%(authorname)'
        out = self._run(['for-each-ref', f'--format={fmt}', 'refs/heads/'])
        branches: list[BranchRef] = []
        for line in out.splitlines():
            if not line.strip():
                continue
            parts = line.split('\t')
            if len(parts) < 2:
                continue
            name, tip = parts[0], parts[1]
            tip_date = _parse_iso(parts[2]) if len(parts) > 2 else None
            tip_author = parts[3] if len(parts) > 3 and parts[3] else None
            branches.append(
                BranchRef(name=name, tip_sha=tip, tip_date=tip_date, tip_author=tip_author)
            )
        return sorted(branches, key=lambda b: b.name)

    def ensure_branch(self, name: str) -> str:
        """Return the verified branch name or raise."""

        for branch in self.list_branches():
            if branch.name == name:
                return branch.name
        raise UnknownRefError(f'unknown branch: {name}')

    def ensure_author(self, email: str) -> str:
        """Return the verified canonical (mailmap-resolved) author email or raise."""

        for author in self.list_authors():
            if author.email == email:
                return author.email
        raise UnknownAuthorError(f'unknown author: {email}')

    def list_commits(
        self,
        branch: str,
        *,
        limit: int = 50,
        skip: int = 0,
        author: str | None = None,
    ) -> list[Commit]:
        ref = self.ensure_branch(branch)
        limit = max(1, min(limit, 200))
        skip = max(0, skip)
        fmt = '%H%x09%h%x09%aN%x09%aE%x09%aI%x09%s'
        args = [
            'log',
            '--use-mailmap',
            '--no-merges',
            f'--pretty=format:{fmt}',
            f'-n{limit}',
            f'--skip={skip}',
        ]
        if author is not None:
            # --use-mailmap makes git resolve --author against the canonical
            # identity too, so matching the email list_authors() already
            # returns is enough. Angle brackets keep the match exact: a bare
            # email would also match it as a substring of an unrelated one.
            canonical_email = self.ensure_author(author)
            args += ['-F', f'--author=<{canonical_email}>']
        args.append(ref)
        out = self._run(args)
        commits: list[Commit] = []
        for line in out.splitlines():
            if not line.strip():
                continue
            parts = line.split('\t', 5)
            if len(parts) < 6:
                continue
            authored = _parse_iso(parts[4])
            if authored is None:
                continue
            commits.append(
                Commit(
                    sha=parts[0],
                    short_sha=parts[1],
                    author_name=parts[2],
                    author_email=parts[3],
                    authored_at=authored,
                    subject=parts[5],
                )
            )
        return commits

    def list_commit_dates(self, branch: str, *, author: str | None = None) -> list[datetime]:
        """Return authored-at timestamps for every non-merge commit on branch.

        Dates only (`%aI`), no other fields — unlike `list_commits`, this is
        not paged, so activity trends can cover the whole history instead of
        a bounded window. The `run_git` output-size limit still applies and
        raises `GitCommandError` if even the dates alone are too large.
        """

        ref = self.ensure_branch(branch)
        args = ['log', '--use-mailmap', '--no-merges', '--format=%aI']
        if author is not None:
            canonical_email = self.ensure_author(author)
            args += ['-F', f'--author=<{canonical_email}>']
        args.append(ref)
        out = self._run(args)
        dates: list[datetime] = []
        for line in out.splitlines():
            text = line.strip()
            if not text:
                continue
            parsed = _parse_iso(text)
            if parsed is not None:
                dates.append(parsed)
        return dates

    def list_authors(self) -> list[Author]:
        # `shortlog` already aggregates and applies mailmap, so the output
        # stays small even on a repository with a huge commit history —
        # unlike `git log` over the full history, it cannot exceed the
        # output size limit. The revision must be explicit: in a bare
        # repository, `shortlog` with no revision silently returns nothing.
        out = self._run(['shortlog', '-sne', '--no-merges', 'HEAD'])
        authors: list[Author] = []
        for line in out.splitlines():
            if not line.strip():
                continue
            count_text, sep, rest = line.partition('\t')
            if not sep or not count_text.strip().isdigit():
                continue
            name, sep, email = rest.rpartition(' <')
            if not sep or not email.endswith('>'):
                continue
            authors.append(Author(name=name, email=email[:-1], commits=int(count_text.strip())))
        return sorted(authors, key=lambda a: (-a.commits, a.name.lower()))

    def summary(self) -> RepoSummary:
        head = self._run(['rev-parse', '--abbrev-ref', 'HEAD']).strip() or None
        count_raw = self._run(['rev-list', '--count', 'HEAD']).strip()
        commit_count = int(count_raw) if count_raw.isdigit() else 0
        first_at = None
        last_at = None
        if commit_count:
            # `git log --reverse -n1` limits before reversing, so it returns the
            # newest commit. Root commits are what actually start the history,
            # and a repository can have more than one of them.
            roots_raw = self._run(['log', '--max-parents=0', '--pretty=format:%aI', 'HEAD'])
            root_dates = [d for d in map(_parse_iso, roots_raw.splitlines()) if d is not None]
            first_at = min(root_dates, default=None)
            last_raw = self._run(['log', '--pretty=format:%aI', '-n1', 'HEAD']).strip()
            last_at = _parse_iso(last_raw)
        branches = self.list_branches()
        authors = self.list_authors()
        return RepoSummary(
            path=str(self.path),
            head=head,
            default_branch=head,
            commit_count=commit_count,
            first_commit_at=first_at,
            last_commit_at=last_at,
            branch_count=len(branches),
            author_count=len(authors),
        )


@lru_cache(maxsize=32)
def get_repository(path: str) -> GitRepository:
    """Cached repository facade keyed by resolved path string."""

    return GitRepository(path)
