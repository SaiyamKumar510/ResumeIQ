import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, PlusCircle, Trash2 } from 'lucide-react';
import AnalysisView from '../components/AnalysisView.jsx';
import { ConfirmModal, PageHeader } from '../components/ui.jsx';
import { useToast } from '../components/Toast.jsx';
import { LoadedAnalysis } from './Results.jsx';
import { api } from '../services/api.js';
import { displayName } from '../utils/format.js';

export default function AnalysisDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  async function remove() {
    setBusy(true);
    try {
      await api.deleteAnalysis(id);
      toast.success('Analysis deleted.');
      navigate('/history', { replace: true });
    } catch (e) {
      toast.error(e.message);
      setBusy(false);
      setConfirming(false);
    }
  }

  return (
    <LoadedAnalysis id={id}>
      {(analysis) => (
        <>
          <PageHeader title={displayName(analysis)} subtitle={`Saved analysis #${analysis.id}`}>
            <button className="btn btn-secondary" onClick={() => navigate('/history')}><ArrowLeft size={16} />Back to history</button>
            <button className="btn btn-secondary" onClick={() => setConfirming(true)}><Trash2 size={16} />Delete</button>
            <button className="btn btn-primary" onClick={() => navigate('/analyze')}><PlusCircle size={16} />New analysis</button>
          </PageHeader>
          <AnalysisView analysis={analysis} />
          <ConfirmModal
            open={confirming} busy={busy} title="Delete this analysis?"
            message="This permanently removes the saved analysis and its stored resume text. This cannot be undone."
            confirmLabel="Delete" onConfirm={remove} onCancel={() => setConfirming(false)}
          />
        </>
      )}
    </LoadedAnalysis>
  );
}
