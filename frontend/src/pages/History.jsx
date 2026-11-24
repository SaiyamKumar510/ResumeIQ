import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ChevronLeft, ChevronRight, Eye, History as HistoryIcon, PlusCircle, Search, SearchX, Trash2 } from 'lucide-react';
import { ConfirmModal, EmptyState, ErrorState, PageHeader, Skeleton } from '../components/ui.jsx';
import { useToast } from '../components/Toast.jsx';
import { useAsync } from '../hooks.js';
import { api } from '../services/api.js';
import { displayName, formatDate, pct, scoreTone } from '../utils/format.js';

const PAGE_SIZE = 10;

export default function History() {
  const navigate = useNavigate();
  const toast = useToast();
  const { loading, error, data, reload } = useAsync(() => api.listAllAnalyses(), []);
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [target, setTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const filtered = useMemo(() => {
    const items = data ? data.analyses : [];
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((a) =>
      [displayName(a), a.job_description_preview, formatDate(a.created_at), String(a.id)].some((v) => (v || '').toLowerCase().includes(q)),
    );
  }, [data, query]);

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const current = Math.min(page, pages);
  const rows = filtered.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);

  async function confirmDelete() {
    setDeleting(true);
    try {
      await api.deleteAnalysis(target.id);
      toast.success('Analysis deleted.');
      setTarget(null);
      reload();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setDeleting(false);
    }
  }

  const header = (
    <PageHeader title="History" subtitle="Every analysis you have run.">
      <button className="btn btn-primary" onClick={() => navigate('/analyze')}><PlusCircle size={16} />New analysis</button>
    </PageHeader>
  );

  if (loading) {
    return <>{header}<div className="card">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} height={22} style={{ margin: '18px 0' }} />)}</div></>;
  }
  if (error) return <>{header}<div className="card"><ErrorState title="Could not load history" message={error.message} onRetry={reload} /></div></>;
  if (data.total === 0) {
    return (
      <>{header}
        <div className="card">
          <EmptyState icon={HistoryIcon} title="No saved analyses" text="Analyses you run will appear here so you can compare them over time.">
            <Link to="/analyze" className="btn btn-primary">Run an analysis</Link>
          </EmptyState>
        </div>
      </>
    );
  }

  return (
    <>
      {header}
      <div className="card">
        <div className="toolbar">
          <div className="search">
            <Search size={16} />
            <input className="input" type="search" placeholder="Search by filename, job text or date" aria-label="Search analyses"
              value={query} onChange={(e) => { setQuery(e.target.value); setPage(1); }} />
          </div>
          <span className="muted small">{filtered.length} of {data.total} analyses</span>
        </div>

        {filtered.length === 0 ? (
          <EmptyState icon={SearchX} title="No matches" text={`Nothing matches “${query}”.`}>
            <button className="btn btn-secondary" onClick={() => setQuery('')}>Clear search</button>
          </EmptyState>
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Resume</th><th>Date</th><th className="num">Score</th><th className="num">Similarity</th><th className="num">Skills</th><th /></tr>
                </thead>
                <tbody>
                  {rows.map((a) => (
                    <tr key={a.id}>
                      <td className="name">
                        <strong>{displayName(a)}</strong>
                        <span className="muted small" style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.job_description_preview}</span>
                      </td>
                      <td className="muted" style={{ whiteSpace: 'nowrap' }}>{formatDate(a.created_at)}</td>
                      <td className="num"><span className={`score-pill ${scoreTone(a.overall_score)}`}>{pct(a.overall_score)}</span></td>
                      <td className="num">{pct(a.text_similarity)}</td>
                      <td className="num"><span className="chip good">{a.matched_skills_count}</span> <span className="chip bad">{a.missing_skills_count}</span></td>
                      <td className="actions">
                        <button className="btn btn-secondary btn-sm" onClick={() => navigate(`/history/${a.id}`)}><Eye size={15} />View</button>{' '}
                        <button className="btn btn-ghost btn-sm icon-btn" aria-label={`Delete analysis ${a.id}`} onClick={() => setTarget(a)}><Trash2 size={16} /></button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="history-cards">
              {rows.map((a) => (
                <div className="hcard" key={a.id}>
                  <div className="hcard-top">
                    <div><strong>{displayName(a)}</strong><div className="muted small">{formatDate(a.created_at)}</div></div>
                    <span className={`score-pill ${scoreTone(a.overall_score)}`}>{pct(a.overall_score)}</span>
                  </div>
                  <div className="chips"><span className="chip good">{a.matched_skills_count} matched</span><span className="chip bad">{a.missing_skills_count} missing</span></div>
                  <div className="row-actions">
                    <button className="btn btn-secondary btn-sm" onClick={() => navigate(`/history/${a.id}`)}><Eye size={15} />View details</button>
                    <button className="btn btn-secondary btn-sm" onClick={() => setTarget(a)}><Trash2 size={15} />Delete</button>
                  </div>
                </div>
              ))}
            </div>

            {pages > 1 && (
              <div className="pager">
                <span className="muted small">Page {current} of {pages}</span>
                <div className="btns">
                  <button className="btn btn-secondary btn-sm" disabled={current === 1} onClick={() => setPage(current - 1)}><ChevronLeft size={15} />Previous</button>
                  <button className="btn btn-secondary btn-sm" disabled={current === pages} onClick={() => setPage(current + 1)}>Next<ChevronRight size={15} /></button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <ConfirmModal open={!!target} busy={deleting} title="Delete this analysis?"
        message={target ? `“${displayName(target)}” from ${formatDate(target.created_at)} will be permanently removed. This cannot be undone.` : ''}
        confirmLabel="Delete" onConfirm={confirmDelete} onCancel={() => setTarget(null)} />
    </>
  );
}
