export type Author = {
  name: string
  email: string
  commits: number
}

export type BranchRef = {
  name: string
  tip_sha: string
  tip_date: string | null
  tip_author: string | null
}

export type Commit = {
  sha: string
  short_sha: string
  author_name: string
  author_email: string
  authored_at: string
  subject: string
}

export type RepoSummary = {
  path: string
  head: string | null
  default_branch: string | null
  commit_count: number
  first_commit_at: string | null
  last_commit_at: string | null
  branch_count: number
  author_count: number
}

export type AuthorContribution = {
  name: string
  email: string
  commits: number
  insertions: number
  deletions: number
  share_percent: number
}

export type ActivityBucket = {
  period: string
  commits: number
}

export type RepoInfo = {
  id: string
  url: string
  path: string
  cloned_at: string
}

/** Thrown for any non-2xx API response; `status` lets callers tell apart,
 * for example, "no repository selected yet" (422) from a real failure. */
export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function apiBase(): string {
  const mount = window.__GITPULSE_MOUNT__ ?? '/git'
  return `${mount.replace(/\/$/, '')}/api/v1`
}

async function readDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string }
    return body.detail ?? ''
  } catch {
    return ''
  }
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`)
  if (!response.ok) {
    const detail = await readDetail(response)
    throw new ApiError(response.status, detail || `request failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    const detail = await readDetail(response)
    throw new ApiError(response.status, detail || `request failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

function authorParam(author: string): string {
  return author ? `author=${encodeURIComponent(author)}` : ''
}

function repoParam(repo: string): string {
  return repo ? `repo=${encodeURIComponent(repo)}` : ''
}

function query(...parts: string[]): string {
  const joined = parts.filter(Boolean).join('&')
  return joined ? `?${joined}` : ''
}

export const api = {
  summary: (repo = '') => getJson<RepoSummary>(`/summary${query(repoParam(repo))}`),
  branches: (repo = '') => getJson<BranchRef[]>(`/branches${query(repoParam(repo))}`),
  commits: (branch: string, author = '', repo = '') =>
    getJson<Commit[]>(
      `/commits${query(`branch=${encodeURIComponent(branch)}`, authorParam(author), repoParam(repo))}`
    ),
  authors: (repo = '') => getJson<Author[]>(`/authors${query(repoParam(repo))}`),
  contributions: (repo = '') =>
    getJson<AuthorContribution[]>(`/contributions${query(repoParam(repo))}`),
  activity: (author = '', repo = '') =>
    getJson<ActivityBucket[]>(`/activity${query(authorParam(author), repoParam(repo))}`),
  repos: () => getJson<RepoInfo[]>('/repos'),
  addRepo: (url: string) => postJson<RepoInfo>('/repos', { url }),
}
