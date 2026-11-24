import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { History as HistoryIcon, PlusCircle, FileX } from 'lucide-react';
import AnalysisView from '../components/AnalysisView.jsx';
import { EmptyState, ErrorState, PageHeader, Skeleton } from '../components/ui.jsx';
import { useAsync } from '../hooks.js';
import { api } from '../services/api.js';

export function DetailSkeleton() {
  return (
    <div className="stack">
      <div className="card"><Skeleton height={170} /></div>
      <div className="grid cols-2"><div className="card"><Skeleton height={110} /></div><div className="card"><Skeleton height={110} /></div></div>
      <div className="card"><Skeleton height={160} /></div>
    </div>
  );
}

export function LoadedAnalysis({ id, preloaded, children }) {
  const { loading, error, data, reload } = useAsync(
    () => (preloaded && String(preloaded.id) === String(id) ? Promise.resolve(preloaded) : api.getAnalysis(id)),
    [id],
  );
  if (loading) return <DetailSkeleton />;
  if (error) {
    if (error.status === 404) {
      return (
        <div className="card">
          <EmptyState icon={FileX} title="Analysis not found" text="It may have been deleted.">
            <Link to="/history" className="btn btn-primary">Back to history</Link>
          </EmptyState>
        </div>
      );
    }
    return <div className="card"><ErrorState title="Could not load the analysis" message={error.message} onRetry={reload} /></div>;
  }
  return children(data);
}

export default function Results() {
  const { id } = useParams();
  const { state } = useLocation();
  const navigate = useNavigate();

  return (
    <>
      <PageHeader title="Analysis results" subtitle="Your resume compared with the job description.">
        <button className="btn btn-secondary" onClick={() => navigate('/history')}><HistoryIcon size={16} />View history</button>
        <button className="btn btn-primary" onClick={() => navigate('/analyze')}><PlusCircle size={16} />Analyze another resume</button>
      </PageHeader>
      <LoadedAnalysis id={id} preloaded={state && state.analysis}>
        {(analysis) => <AnalysisView analysis={analysis} />}
      </LoadedAnalysis>
    </>
  );
}
