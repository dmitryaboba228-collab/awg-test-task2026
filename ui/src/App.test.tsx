import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'

describe('App', () => {
  it('shows loading state', () => {
    render(<App />)
    expect(screen.getByText(/Loading/i)).toBeTruthy()
  })
})

const summary = {
  path: '/repo',
  head: 'main',
  default_branch: 'main',
  commit_count: 2,
  first_commit_at: null,
  last_commit_at: null,
  branch_count: 1,
  author_count: 2,
}

const branches = [{ name: 'main', tip_sha: 'abc', tip_date: null, tip_author: null }]

const authors = [
  { name: 'Ada Lovelace', email: 'ada@example.com', commits: 1 },
  { name: 'Bob B.', email: 'bob@example.com', commits: 1 },
]

const contributions = [
  {
    name: 'Ada Lovelace',
    email: 'ada@example.com',
    commits: 1,
    insertions: 0,
    deletions: 0,
    share_percent: 50,
  },
  {
    name: 'Bob B.',
    email: 'bob@example.com',
    commits: 1,
    insertions: 0,
    deletions: 0,
    share_percent: 50,
  },
]

const allCommits = [
  {
    sha: 's1',
    short_sha: 's1',
    author_name: 'Ada Lovelace',
    author_email: 'ada@example.com',
    authored_at: '2024-01-01T00:00:00Z',
    subject: 'feat: one',
  },
  {
    sha: 's2',
    short_sha: 's2',
    author_name: 'Bob B.',
    author_email: 'bob@example.com',
    authored_at: '2024-01-02T00:00:00Z',
    subject: 'feat: two',
  },
]
const adaCommits = allCommits.filter((commit) => commit.author_email === 'ada@example.com')

const activityAll = [{ period: '2024-W01', commits: 2 }]
const activityAda = [{ period: '2024-W01', commits: 1 }]

function jsonResponse(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as Response
}

/** `getByTitle` only matches a `<title>` that is a direct child of `<svg>`
 * (the chart's own title), not one nested in a bar's `<rect>` — so per-bar
 * tooltips need a plain content match instead. */
function getByBarTooltip(text: string): SVGTitleElement {
  const match = screen.getByText(
    (_, element) => element?.tagName.toLowerCase() === 'title' && element.textContent === text,
  )
  return match as unknown as SVGTitleElement
}

describe('App author filter', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input)
        const filteredByAda = url.includes('author=ada%40example.com')
        // Single repo_path mode: no connected workspace repos, every other
        // call omits `repo` and resolves against the host's fixed repo.
        if (url.includes('/repos')) return Promise.resolve(jsonResponse([]))
        if (url.includes('/summary')) return Promise.resolve(jsonResponse(summary))
        if (url.includes('/branches')) return Promise.resolve(jsonResponse(branches))
        if (url.includes('/authors')) return Promise.resolve(jsonResponse(authors))
        if (url.includes('/contributions')) return Promise.resolve(jsonResponse(contributions))
        if (url.includes('/commits')) {
          return Promise.resolve(jsonResponse(filteredByAda ? adaCommits : allCommits))
        }
        if (url.includes('/activity')) {
          return Promise.resolve(jsonResponse(filteredByAda ? activityAda : activityAll))
        }
        return Promise.reject(new Error(`unexpected request: ${url}`))
      }),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('narrows the commit feed and activity trend to the selected author', async () => {
    render(<App />)

    await waitFor(() => expect(screen.getByText('feat: two')).toBeTruthy())
    await waitFor(() => expect(getByBarTooltip('2024-W01: 2 commits')).toBeTruthy())

    const authorSelect = screen.getByLabelText('Author') as HTMLSelectElement
    fireEvent.change(authorSelect, { target: { value: 'ada@example.com' } })

    await waitFor(() => expect(screen.queryByText('feat: two')).toBeNull())
    expect(screen.getByText('feat: one')).toBeTruthy()
    await waitFor(() => expect(getByBarTooltip('2024-W01: 1 commit')).toBeTruthy())
  })

  it('highlights the selected author in the contribution share list', async () => {
    render(<App />)
    await waitFor(() => expect(screen.getByText('feat: two')).toBeTruthy())

    const authorSelect = screen.getByLabelText('Author') as HTMLSelectElement
    fireEvent.change(authorSelect, { target: { value: 'bob@example.com' } })

    const contributionsPanel = screen
      .getByRole('heading', { name: 'Contribution share' })
      .closest('div') as HTMLElement
    await waitFor(() => {
      const row = within(contributionsPanel).getByText('Bob B.').closest('li')
      expect(row?.className).toContain('active')
    })
  })

  it('connects a new repository through the form', async () => {
    const fetchMock = vi.mocked(fetch)
    render(<App />)
    await waitFor(() => expect(screen.getByText('feat: two')).toBeTruthy())

    fetchMock.mockImplementationOnce(() =>
      Promise.resolve(
        jsonResponse({
          id: 'demo-repo',
          url: 'https://example.com/demo.git',
          path: '/workspace/demo-repo',
          cloned_at: '2024-01-01T00:00:00Z',
        }),
      ),
    )

    const input = screen.getByPlaceholderText('https://github.com/owner/name.git')
    fireEvent.change(input, { target: { value: 'https://example.com/demo.git' } })
    const form = input.closest('form') as HTMLFormElement
    fireEvent.submit(form)

    await waitFor(() => expect(screen.getByText('https://example.com/demo.git')).toBeTruthy())
  })
})
