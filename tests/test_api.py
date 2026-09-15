"""API route tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get('/git/api/v1/health')
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'ok'
    assert body['version']


def test_summary_and_branches(client: TestClient) -> None:
    summary = client.get('/git/api/v1/summary')
    assert summary.status_code == 200
    assert summary.json()['commit_count'] == 2
    branches = client.get('/git/api/v1/branches')
    assert branches.status_code == 200
    names = {row['name'] for row in branches.json()}
    assert 'main' in names


def test_commits_and_authors(client: TestClient) -> None:
    commits = client.get('/git/api/v1/commits', params={'branch': 'main'})
    assert commits.status_code == 200
    assert len(commits.json()) >= 2
    authors = client.get('/git/api/v1/authors')
    assert authors.status_code == 200
    assert authors.json()[0]['name'] == 'Ada Lovelace'


def test_unknown_branch(client: TestClient) -> None:
    response = client.get('/git/api/v1/commits', params={'branch': 'does-not-exist'})
    assert response.status_code == 404


def test_branch_with_slash(client: TestClient) -> None:
    response = client.get('/git/api/v1/commits', params={'branch': 'feat/sample'})
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_commits_filtered_by_author(two_author_client: TestClient) -> None:
    response = two_author_client.get(
        '/git/api/v1/commits', params={'branch': 'main', 'author': 'ada@example.com'}
    )
    assert response.status_code == 200
    rows = response.json()
    assert rows
    assert all(row['author_email'] == 'ada@example.com' for row in rows)


def test_commits_unknown_author_is_404(two_author_client: TestClient) -> None:
    response = two_author_client.get(
        '/git/api/v1/commits', params={'branch': 'main', 'author': 'nope@example.com'}
    )
    assert response.status_code == 404


def test_activity_filtered_by_author(two_author_client: TestClient) -> None:
    response = two_author_client.get('/git/api/v1/activity', params={'author': 'ada@example.com'})
    assert response.status_code == 200
    assert sum(bucket['commits'] for bucket in response.json()) == 2


def test_activity_unknown_author_is_404(two_author_client: TestClient) -> None:
    response = two_author_client.get('/git/api/v1/activity', params={'author': 'nope@example.com'})
    assert response.status_code == 404


def test_authors_endpoint_lists_canonical_identities(two_author_client: TestClient) -> None:
    response = two_author_client.get('/git/api/v1/authors')
    assert response.status_code == 200
    emails = {row['email'] for row in response.json()}
    assert emails == {'ada@example.com', 'bob@example.com', 'nomada@example.com'}
