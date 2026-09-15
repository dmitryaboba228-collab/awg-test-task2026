"""Simplify contribution calculation."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from gitpulse.core.models import ActivityBucket, AuthorContribution
from gitpulse.git.repository import GitRepository


def author_contributions(
    repo: GitRepository,
    *,
    branch: str | None = None,
    limit_commits: int = 500,
    author: str | None = None,
) -> list[AuthorContribution]:
    """Estimate contribution share from commit counts (mailmap-aware).

    Full `--numstat` line accounting is left to candidates extending the module.
    The reference uses commit counts for a fast, bounded baseline.

    With no `branch` and no `author`, this uses the cheap aggregate path
    (`GitRepository.list_authors`, backed by `git shortlog`) instead of
    walking commits one by one.
    """

    if branch is None and author is None:
        authors = repo.list_authors()
        total = sum(a.commits for a in authors) or 1
        return [
            AuthorContribution(
                name=a.name,
                email=a.email,
                commits=a.commits,
                share_percent=round(100.0 * a.commits / total, 2),
            )
            for a in authors
        ]

    ref = branch or (repo.summary().head or 'main')
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for commit in repo.list_commits(ref, limit=limit_commits, author=author):
        counts[(commit.author_name, commit.author_email)] += 1
    total = sum(counts.values()) or 1
    return [
        AuthorContribution(
            name=name,
            email=email,
            commits=count,
            share_percent=round(100.0 * count / total, 2),
        )
        for (name, email), count in sorted(counts.items(), key=lambda item: (-item[1], item[0][0]))
    ]


def activity_by_week(
    repo: GitRepository,
    *,
    branch: str | None = None,
    limit_commits: int = 500,
    author: str | None = None,
) -> list[ActivityBucket]:
    """Bucket recent commits by ISO week."""

    head = repo.summary().head or 'main'
    ref = branch or head
    buckets: dict[str, int] = defaultdict(int)
    for commit in repo.list_commits(ref, limit=limit_commits, author=author):
        week = _iso_week(commit.authored_at)
        buckets[week] += 1
    return [
        ActivityBucket(period=period, commits=count) for period, count in sorted(buckets.items())
    ]


def _iso_week(value: datetime) -> str:
    year, week, _ = value.isocalendar()
    return f'{year}-W{week:02d}'
