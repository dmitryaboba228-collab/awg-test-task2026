"""Tests for the git adapter and analytics."""

from __future__ import annotations

from pathlib import Path

import pytest

from gitpulse.analytics import activity_by_week, author_contributions
from gitpulse.git.errors import UnknownAuthorError
from gitpulse.git.repository import GitRepository


def test_list_branches_and_commits(sample_repo: Path) -> None:
    repo = GitRepository(sample_repo)
    names = {b.name for b in repo.list_branches()}
    assert 'main' in names
    assert 'feat/sample' in names
    commits = repo.list_commits('main')
    assert len(commits) >= 2
    assert commits[0].subject


def test_mailmap_collapses_authors(sample_repo: Path) -> None:
    repo = GitRepository(sample_repo)
    authors = repo.list_authors()
    assert len(authors) == 1
    assert authors[0].name == 'Ada Lovelace'
    assert authors[0].commits == 2


def test_summary(sample_repo: Path) -> None:
    summary = GitRepository(sample_repo).summary()
    assert summary.commit_count == 2
    assert summary.branch_count == 2
    assert summary.author_count == 1


def test_contributions_share(sample_repo: Path) -> None:
    repo = GitRepository(sample_repo)
    rows = author_contributions(repo)
    assert rows
    assert abs(sum(r.share_percent for r in rows) - 100.0) < 0.1


def test_list_authors_via_shortlog(two_author_repo: Path) -> None:
    repo = GitRepository(two_author_repo)
    authors = {a.email: a.commits for a in repo.list_authors()}
    assert authors == {
        'ada@example.com': 2,
        'bob@example.com': 1,
        'nomada@example.com': 1,
    }


def test_ensure_author_rejects_unknown_email(two_author_repo: Path) -> None:
    repo = GitRepository(two_author_repo)
    assert repo.ensure_author('ada@example.com') == 'ada@example.com'
    with pytest.raises(UnknownAuthorError):
        repo.ensure_author('nope@example.com')


def test_list_commits_filters_by_author(two_author_repo: Path) -> None:
    repo = GitRepository(two_author_repo)
    commits = repo.list_commits('main', author='ada@example.com')
    assert len(commits) == 2
    assert all(c.author_email == 'ada@example.com' for c in commits)


def test_list_commits_author_filter_uses_mailmap_alias(two_author_repo: Path) -> None:
    """Filtering by the canonical email also picks up the aliased commit."""

    repo = GitRepository(two_author_repo)
    commits = repo.list_commits('main', author='ada@example.com')
    subjects = {c.subject for c in commits}
    assert subjects == {'feat: one', 'docs: expand readme'}


def test_list_commits_author_filter_is_exact_not_substring(two_author_repo: Path) -> None:
    """A decoy author (`nomada`) must not match an `ada` filter."""

    repo = GitRepository(two_author_repo)
    commits = repo.list_commits('main', author='ada@example.com')
    assert all('nomada' not in c.author_email for c in commits)

    nomada_commits = repo.list_commits('main', author='nomada@example.com')
    assert len(nomada_commits) == 1
    assert nomada_commits[0].author_email == 'nomada@example.com'


def test_list_commits_unknown_author_raises(two_author_repo: Path) -> None:
    repo = GitRepository(two_author_repo)
    with pytest.raises(UnknownAuthorError):
        repo.list_commits('main', author='nope@example.com')


def test_activity_by_week_filters_by_author(two_author_repo: Path) -> None:
    repo = GitRepository(two_author_repo)
    all_weeks = activity_by_week(repo)
    ada_weeks = activity_by_week(repo, author='ada@example.com')
    assert sum(b.commits for b in ada_weeks) == 2
    assert sum(b.commits for b in ada_weeks) < sum(b.commits for b in all_weeks)


def test_author_contributions_filters_by_author(two_author_repo: Path) -> None:
    repo = GitRepository(two_author_repo)
    rows = author_contributions(repo, author='ada@example.com')
    assert {r.email for r in rows} == {'ada@example.com'}
    assert rows[0].commits == 2
