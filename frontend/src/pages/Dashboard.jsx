import { Link, useNavigate } from 'react-router-dom';
import { BarChart3, ChevronRight, FileSearch, ListChecks, PlusCircle, Target, Trophy } from 'lucide-react';
import { EmptyState, ErrorState, PageHeader, Skeleton, StatCard } from '../components/ui.jsx';
import { useAsync } from '../hooks.js';
import { api } from '../services/api.js';
import { displayName, formatDate, pct, scoreTone } from '../utils/format.js';

const mean = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);

export default function Dashboard() {
  const navigate = useNavigate();
  const { loading, error, data, reload } = useAsync(() => api.listAllAnalyses(), []);

  const header = (
    <PageHeader title="Welcome back" subtitle="Track how well your resumes match the roles you are targeting.">
      <button className="btn btn-primary btn-lg" onClick={() => navigate('/analyze')}><PlusCircle size={18} />New analysis</button>
    </PageHeader>
  );

  if (loading) {
    return (
      <>
        {header}
        <div className="grid cols-4">{[0, 1, 2, 3].map((i) => <div className="card" key={i}><Skeleton height={14} width="50%" /><Skeleton height={30} width="40%" style={{ marginTop: 14 }} /></div>)}</div>
        <div className="grid main-side" style={{ marginTop: 18 }}><div className="card"><Skeleton height={190} /></div><div className="card"><Skeleton height={190} /></div></div>
      </>
    );
  }
  if (error) {
    return <>{header}<div className="card"><ErrorState title="Could not load your analyses" message={error.message} onRetry={reload} /></div></>;
  }

  const { total, analyses } = data;
  if (total === 0) {
    return (
      <>
        {header}
        <div className="card">
          <EmptyState icon={FileSearch} title="No analyses yet"
            text="Upload a resume and paste a job description to see your estimated compatibility score, matched skills and gaps.">
            <Link to="/analyze" className="btn btn-primary btn-lg"><PlusCircle size={18} />Run your first analysis</Link>
          </EmptyState>
        </div>
      </>
    );
  }

  const scores = analyses.map((a) => a.overall_score);
  const coverages = analyses.map((a) => a.skill_coverage).filter((v) => v !== null && v !== undefined);
  const best = Math.max(...scores);
  const avg = mean(scores);
  const avgCoverage = mean(coverages);
  const trend = analyses.slice(0, 10).reverse(); // oldest -> newest
  const recent = analyses.slice(0, 5);

  return (
    <>
      {header}
      <div className="grid cols-4">
        <StatCard label="Total analyses" value={total} icon={ListChecks} sub="Saved in your history" />
        <StatCard label="Average score" value={pct(avg)} icon={BarChart3} sub={`Across ${analyses.length} analys${analyses.length === 1 ? 'is' : 'es'}`} />
        <StatCard label="Best score" value={pct(best)} icon={Trophy} sub="Highest estimated match" />
        <StatCard label="Avg. skill coverage" value={pct(avgCoverage)} icon={Target}
          sub={coverages.length ? `Across ${coverages.length} with detected skills` : 'No skills detected yet'} />
      </div>

      <div className="grid main-side" style={{ marginTop: 18, alignItems: 'start' }}>
        <section className="card">
          <div className="card-head"><h2>Recent analyses</h2><Link to="/history" className="btn btn-ghost btn-sm">View all<ChevronRight size={15} /></Link></div>
          <div className="recent">
            {recent.map((a) => (
              <Link key={a.id} to={`/history/${a.id}`} className="recent-item">
                <div className="grow"><strong>{displayName(a)}</strong><span className="muted small">{formatDate(a.created_at)}</span></div>
                <span className={`score-pill ${scoreTone(a.overall_score)}`}>{pct(a.overall_score)}</span>
                <ChevronRight size={16} className="muted" />
              </Link>
            ))}
          </div>
        </section>

        <section className="card">
          <div className="card-head"><h2>Score trend</h2><span className="muted small">Last {trend.length}</span></div>
          <div className="trend" role="img" aria-label="Bar chart of overall scores for the latest analyses">
            {trend.map((a) => (
              <div className="trend-col" key={a.id} title={`${displayName(a)} · ${pct(a.overall_score)} · ${formatDate(a.created_at)}`}>
                <span className="trend-lbl">{Math.round(a.overall_score)}</span>
                <div className={`trend-bar ${scoreTone(a.overall_score)}`} style={{ height: `${Math.max(2, a.overall_score)}%` }} />
              </div>
            ))}
          </div>
          <div className="legend"><span><i className="good" />70%+</span><span><i />40–69%</span><span><i className="low" />Below 40%</span></div>
        </section>
      </div>
    </>
  );
}
