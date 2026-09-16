"""REST routes for repository metadata."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from gitpulse import __version__
from gitpulse.analytics import activity_by_week, author_contributions
from gitpulse.core.models import (
    ActivityBucket,
    Author,
    AuthorContribution,
    BranchRef,
    Commit,
    RepoInfo,
    RepoSummary,
)
from gitpulse.git.clone import InvalidRepoUrlError
from gitpulse.git.errors import GitPulseError, UnknownAuthorError, UnknownRefError
from gitpulse.git.registry import RepoRegistry, UnknownRepoError
from gitpulse.git.repository import GitRepository


class RepoCreate(BaseModel):
    """Request body for `POST /repos`."""

    url: str


def build_api_router(
    repository: GitRepository | None = None,
    registry: RepoRegistry | None = None,
    *,
    api_prefix: str = '/api/v1',
) -> APIRouter:
    router = APIRouter(prefix=api_prefix, tags=['gitpulse'])

    def _repo_for(repo: str | None) -> GitRepository:
        """Resolve the repository for a request.

        A fixed `repository` (single-repo mode) always wins, so callers do
        not need to pass `repo` there. Otherwise `repo` selects a clone from
        the workspace `registry`.
        """

        if repository is not None:
            return repository
        if registry is None:
            raise HTTPException(status_code=400, detail='no repository configured')
        if repo is None:
            raise HTTPException(status_code=422, detail='repo query parameter is required')
        try:
            return registry.get(repo)
        except UnknownRepoError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get('/health')
    def health() -> dict[str, str]:
        return {'status': 'ok', 'version': __version__}

    @router.post('/repos', response_model=RepoInfo, status_code=201)
    def add_repo(payload: RepoCreate) -> RepoInfo:
        if registry is None:
            raise HTTPException(status_code=400, detail='repository workspace is not configured')
        try:
            return registry.add(payload.url)
        except InvalidRepoUrlError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except GitPulseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get('/repos', response_model=list[RepoInfo])
    def list_repos() -> list[RepoInfo]:
        return registry.list() if registry is not None else []

    @router.get('/summary', response_model=RepoSummary)
    def summary(repo: str | None = None) -> RepoSummary:
        try:
            return _repo_for(repo).summary()
        except GitPulseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get('/branches', response_model=list[BranchRef])
    def branches(repo: str | None = None) -> list[BranchRef]:
        try:
            return _repo_for(repo).list_branches()
        except GitPulseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get('/commits', response_model=list[Commit])
    def commits(
        branch: str = Query(..., min_length=1),
        limit: int = Query(default=50, ge=1, le=200),
        skip: int = Query(default=0, ge=0),
        author: str | None = None,
        repo: str | None = None,
    ) -> list[Commit]:
        try:
            return _repo_for(repo).list_commits(branch, limit=limit, skip=skip, author=author)
        except (UnknownRefError, UnknownAuthorError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except GitPulseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get('/authors', response_model=list[Author])
    def authors(repo: str | None = None) -> list[Author]:
        try:
            return _repo_for(repo).list_authors()
        except GitPulseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get('/contributions', response_model=list[AuthorContribution])
    def contributions(
        branch: str | None = None,
        limit_commits: int = Query(default=500, ge=1, le=2000),
        repo: str | None = None,
    ) -> list[AuthorContribution]:
        try:
            return author_contributions(_repo_for(repo), branch=branch, limit_commits=limit_commits)
        except UnknownRefError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except GitPulseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get('/activity', response_model=list[ActivityBucket])
    def activity(
        branch: str | None = None,
        limit_commits: int = Query(default=500, ge=1, le=2000),
        author: str | None = None,
        repo: str | None = None,
    ) -> list[ActivityBucket]:
        try:
            return activity_by_week(
                _repo_for(repo), branch=branch, limit_commits=limit_commits, author=author
            )
        except (UnknownRefError, UnknownAuthorError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except GitPulseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
