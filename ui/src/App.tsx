import { useEffect, useState } from 'react'
import {
  ActivityBucket,
  Author,
  AuthorContribution,
  BranchRef,
  Commit,
  RepoSummary,
  api,
} from './api'

export function App() {
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

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [s, b, a, c] = await Promise.all([
          api.summary(),
          api.branches(),
          api.authors(),
          api.contributions(),
        ])
        if (cancelled) return
        setSummary(s)
        setBranches(b)
        setAuthors(a)
        setContributions(c)
        const initial = s.head || b[0]?.name || ''
        setBranch(initial)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'failed to load')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  // Commit feed: scoped to the selected branch, narrowed to the selected
  // author when one is picked.
  useEffect(() => {
    if (!branch) return
    let cancelled = false
    ;(async () => {
      try {
        const rows = await api.commits(branch, author)
        if (!cancelled) setCommits(rows)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'failed to load commits')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [branch, author])

  // Activity trend: same author filter as the commit feed. Contribution
  // shares stay unfiltered — the selected author is highlighted there
  // instead, so the share of the whole project is still visible.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const rows = await api.activity(author)
        if (!cancelled) setActivity(rows)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'failed to load activity')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [author])

  if (loading) {
    return (
      <div className="shell">
        <p className="muted">Loading repository…</p>
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

  return (
    <div className="shell">
      <header className="hero">
        <p className="brand">AWG GitPulse</p>
        <h1>Repository pulse</h1>
        <p className="lede">
          Local git metadata for <code>{summary?.path}</code>
        </p>
      </header>

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
            Share of non-merge commits per author, whole project — the selected author is
            highlighted, not filtered.
          </p>
          <ul className="list">
            {contributions.map((row) => (
              <li
                key={`${row.name}:${row.email}`}
                className={row.email === author ? 'active' : undefined}
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
        <ul className="activity">
          {activity.map((bucket) => (
            <li key={bucket.period}>
              <span>{bucket.period}</span>
              <strong>{bucket.commits}</strong>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
