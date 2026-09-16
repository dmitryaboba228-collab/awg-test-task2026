import { FormEvent, useEffect, useState } from 'react'
import {
  ActivityBucket,
  ApiError,
  Author,
  AuthorContribution,
  BranchRef,
  Commit,
  RepoInfo,
  RepoSummary,
  api,
} from './api'

const TOP_AUTHOR_COUNT = 5

/** Collapse everyone past the top N into a single "Others" row, so a
 * project with hundreds of authors still renders a readable share list. */
function topContributions(rows: AuthorContribution[]): AuthorContribution[] {
  if (rows.length <= TOP_AUTHOR_COUNT) return rows
  const top = rows.slice(0, TOP_AUTHOR_COUNT)
  const rest = rows.slice(TOP_AUTHOR_COUNT)
  const commits = rest.reduce((sum, row) => sum + row.commits, 0)
  const sharePercent = rest.reduce((sum, row) => sum + row.share_percent, 0)
  return [
    ...top,
    {
      name: `Others (${rest.length})`,
      email: '',
      commits,
      insertions: 0,
      deletions: 0,
      share_percent: Math.round(sharePercent * 100) / 100,
    },
  ]
}

function ActivityChart({ buckets }: { buckets: ActivityBucket[] }) {
  if (buckets.length === 0) {
    return <p className="muted">No commits in this view.</p>
  }
  const max = Math.max(...buckets.map((bucket) => bucket.commits), 1)
  const width = 720
  const height = 160
  const gap = buckets.length > 60 ? 1 : 2
  const barWidth = Math.max(width / buckets.length - gap, 1)
  return (
    <svg
      className="activity-chart"
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      role="img"
      aria-label={`Commits per ISO week across ${buckets.length} weeks`}
    >
      {buckets.map((bucket, index) => {
        const barHeight = (bucket.commits / max) * (height - 4)
        const x = index * (barWidth + gap)
        return (
          <rect
            key={bucket.period}
            x={x}
            y={height - barHeight}
            width={barWidth}
            height={Math.max(barHeight, 1)}
          >
            <title>{`${bucket.period}: ${bucket.commits} commit${bucket.commits === 1 ? '' : 's'}`}</title>
          </rect>
        )
      })}
    </svg>
  )
}

export function App() {
  const [repos, setRepos] = useState<RepoInfo[]>([])
  const [activeRepo, setActiveRepo] = useState('')
  const [repoReady, setRepoReady] = useState(false)
  const [connectUrl, setConnectUrl] = useState('')
  const [connecting, setConnecting] = useState(false)
  const [connectError, setConnectError] = useState<string | null>(null)

  const [summary, setSummary] = useState<RepoSummary | null>(null)
  const [branches, setBranches] = useState<BranchRef[]>([])
  const [branch, setBranch] = useState('')
  const [commits, setCommits] = useState<Commit[]>([])
  const [authors, setAuthors] = useState<Author[]>([])
  const [author, setAuthor] = useState('')
  const [contributions, setContributions] = useState<AuthorContribution[]>([])
  const [activity, setActivity] = useState<ActivityBucket[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  // Connected repositories (workspace mode). A host running with a single
  // fixed repo_path has none of these — that mode keeps working below
  // because every call passes `activeRepo`, which stays '' and lets the
  // server fall back to its fixed repository.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const repoList = await api.repos()
        if (cancelled) return
        setRepos(repoList)
        if (repoList.length > 0) setActiveRepo(repoList[0].id)
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'failed to list repositories')
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  // Repository overview: reloads whenever the active repo changes,
  // including the initial '' selection (single repo_path mode).
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      try {
        const [s, b, a, c] = await Promise.all([
          api.summary(activeRepo),
          api.branches(activeRepo),
          api.authors(activeRepo),
          api.contributions(activeRepo),
        ])
        if (cancelled) return
        setSummary(s)
        setBranches(b)
        setAuthors(a)
        setContributions(c)
        setRepoReady(true)
        setError(null)
        setBranch(s.head || b[0]?.name || '')
        setAuthor('')
      } catch (err) {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 422) {
          // No repository selected yet — an empty workspace, not a failure.
          setRepoReady(false)
          setSummary(null)
        } else {
          setError(err instanceof Error ? err.message : 'failed to load repository')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [activeRepo])

  // Commit feed: scoped to the selected branch, narrowed to the selected
  // author when one is picked.
  useEffect(() => {
    if (!repoReady || !branch) return
    let cancelled = false
    ;(async () => {
      try {
        const rows = await api.commits(branch, author, activeRepo)
        if (!cancelled) setCommits(rows)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'failed to load commits')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [branch, author, activeRepo, repoReady])

  // Activity trend: same author filter as the commit feed, whole history.
  // Contribution shares stay unfiltered — the selected author is
  // highlighted there instead, so the share of the whole project stays
  // visible.
  useEffect(() => {
    if (!repoReady) return
    let cancelled = false
    ;(async () => {
      try {
        const rows = await api.activity(author, activeRepo)
        if (!cancelled) setActivity(rows)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'failed to load activity')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [author, activeRepo, repoReady])

  async function handleConnect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const url = connectUrl.trim()
    if (!url) return
    setConnecting(true)
    setConnectError(null)
    try {
      const info = await api.addRepo(url)
      setRepos((prev) => [...prev.filter((r) => r.id !== info.id), info])
      setConnectUrl('')
      setActiveRepo(info.id)
    } catch (err) {
      setConnectError(err instanceof ApiError ? err.message : 'failed to connect repository')
    } finally {
      setConnecting(false)
    }
  }

  const connectPanel = (
    <section className="panel">
      <h2>Connect a repository</h2>
      <form className="connect-form" onSubmit={handleConnect}>
        <input
          type="url"
          placeholder="https://github.com/owner/name.git"
          value={connectUrl}
          onChange={(e) => setConnectUrl(e.target.value)}
          disabled={connecting}
          required
        />
        <button type="submit" disabled={connecting || !connectUrl.trim()}>
          {connecting ? 'Cloning…' : 'Connect'}
        </button>
      </form>
      {connectError && <p className="error">{connectError}</p>}
      {repos.length > 0 && (
        <label className="branch-select">
          Repository
          <select value={activeRepo} onChange={(e) => setActiveRepo(e.target.value)}>
            {repos.map((repo) => (
              <option key={repo.id} value={repo.id}>
                {repo.url}
              </option>
            ))}
          </select>
        </label>
      )}
    </section>
  )

  if (loading && !repoReady) {
    return (
      <div className="shell">
        <p className="muted">Loading…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="shell">
        <p className="error">{error}</p>
      </div>
    )
  }

  if (!repoReady) {
    return (
      <div className="shell">
        <header className="hero">
          <p className="brand">AWG GitPulse</p>
          <h1>Repository pulse</h1>
          <p className="lede">
            Paste a public repository URL to clone and analyze it — no local checkout needed.
          </p>
        </header>
        {connectPanel}
      </div>
    )
  }

  return (
    <div className="shell">
      <header className="hero">
        <p className="brand">AWG GitPulse</p>
        <h1>Repository pulse</h1>
        <p className="lede">
          Git metadata for <code>{summary?.path}</code>
        </p>
      </header>

      {connectPanel}

      <section className="panel">
        <h2>Overview</h2>
        <dl className="stats">
          <div>
            <dt>Commits</dt>
            <dd>{summary?.commit_count ?? 0}</dd>
          </div>
          <div>
            <dt>Branches</dt>
            <dd>{summary?.branch_count ?? 0}</dd>
          </div>
          <div>
            <dt>Authors</dt>
            <dd>{summary?.author_count ?? 0}</dd>
          </div>
          <div>
            <dt>HEAD</dt>
            <dd>{summary?.head ?? '—'}</dd>
          </div>
        </dl>
      </section>

      <section className="panel">
        <div className="row">
          <h2>Commits</h2>
          <div className="row" style={{ gap: '0.75rem' }}>
            <label className="branch-select">
              Author
              <select value={author} onChange={(e) => setAuthor(e.target.value)}>
                <option value="">All authors</option>
                {authors.map((item) => (
                  <option key={item.email} value={item.email}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="branch-select">
              Branch
              <select value={branch} onChange={(e) => setBranch(e.target.value)}>
                {branches.map((item) => (
                  <option key={item.name} value={item.name}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
        {author && commits.length === 0 ? (
          <p className="muted">No commits by this author on {branch}.</p>
        ) : (
          <ol className="timeline">
            {commits.map((commit) => (
              <li key={commit.sha}>
                <code>{commit.short_sha}</code>
                <strong>{commit.subject}</strong>
                <span className="muted">
                  {commit.author_name} · {new Date(commit.authored_at).toLocaleString()}
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="panel split">
        <div>
          <h2>Authors</h2>
          <ul className="list">
            {authors.map((item) => (
              <li
                key={`${item.name}:${item.email}`}
                className={item.email === author ? 'active' : undefined}
              >
                <strong>{item.name}</strong>
                <span className="muted">
                  {item.email} · {item.commits} commits
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h2>Contribution share</h2>
          <p className="muted">
            Top {TOP_AUTHOR_COUNT} authors by non-merge commits, whole project — the selected
            author is highlighted, not filtered.
          </p>
          <ul className="list">
            {topContributions(contributions).map((row) => (
              <li
                key={`${row.name}:${row.email}`}
                className={row.email && row.email === author ? 'active' : undefined}
              >
                <div className="bar-row">
                  <strong>{row.name}</strong>
                  <span>{row.share_percent}%</span>
                </div>
                <div className="bar">
                  <span style={{ width: `${Math.min(row.share_percent, 100)}%` }} />
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="panel">
        <h2>Activity by week{author ? ' · filtered by author' : ''}</h2>
        <p className="muted">
          Every non-merge commit on {branch || 'the default branch'}, bucketed by ISO week, whole
          history.
        </p>
        <ActivityChart buckets={activity} />
      </section>

      <section className="panel">
        <h2>How metrics are computed</h2>
        <ul className="notes">
          <li>
            <strong>Contribution share</strong> counts non-merge commits per author after applying
            the repository&apos;s <code>.mailmap</code>, not lines changed — a one-line fix and a
            thousand-line refactor count the same.
          </li>
          <li>
            <strong>Authors</strong> come from <code>git shortlog</code>, so aliases in{' '}
            <code>.mailmap</code> are already folded into one canonical identity.
          </li>
          <li>
            <strong>Author filter</strong> matches that canonical email exactly — selecting
            someone shows their commits under every alias they have used.
          </li>
          <li>
            <strong>Activity trend</strong> covers the whole history, not a recent window; very
            large histories can still hit a server-side output-size limit and report an error
            instead of silently truncating.
          </li>
          <li>
            <strong>Cloning</strong> only fetches commit history, not file contents, so the first
            request against a large repository can take a while.
          </li>
        </ul>
      </section>
    </div>
  )
}
