import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, Loader2, Type, Upload, X, AlertTriangle, Sparkles } from 'lucide-react';
import { PageHeader } from '../components/ui.jsx';
import { useToast } from '../components/Toast.jsx';
import { api } from '../services/api.js';

const MAX_MB = Number(import.meta.env.VITE_MAX_UPLOAD_MB) || 5;

function formatSize(bytes) {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function Analyze() {
  const navigate = useNavigate();
  const toast = useToast();
  const inputRef = useRef(null);
  const submitting = useRef(false);

  const [mode, setMode] = useState('pdf');
  const [file, setFile] = useState(null);
  const [fileError, setFileError] = useState('');
  const [resumeText, setResumeText] = useState('');
  const [jd, setJd] = useState('');
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState('');

  function pickFile(f) {
    setFileError('');
    if (!f) return;
    if (!f.name.toLowerCase().endsWith('.pdf')) { setFileError('Only PDF files are supported.'); return; }
    if (f.size === 0) { setFileError('This file is empty.'); return; }
    if (f.size > MAX_MB * 1024 * 1024) { setFileError(`This file is ${formatSize(f.size)}. The limit is ${MAX_MB} MB.`); return; }
    setFile(f);
    setErrors((e) => ({ ...e, resume: undefined }));
  }

  function onDrop(e) {
    e.preventDefault();
    setDragOver(false);
    if (loading) return;
    pickFile(e.dataTransfer.files && e.dataTransfer.files[0]);
  }

  function validate() {
    const next = {};
    if (mode === 'pdf' && !file) next.resume = 'Upload a PDF resume.';
    if (mode === 'text' && !resumeText.trim()) next.resume = 'Paste your resume text.';
    if (!jd.trim()) next.jd = 'Paste the job description.';
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  async function submit(e) {
    e.preventDefault();
    if (submitting.current) return; // prevents duplicate submissions
    setServerError('');
    if (!validate()) return;
    submitting.current = true;
    setLoading(true);
    try {
      const result = mode === 'pdf'
        ? await api.analyzePdf({ file, jobDescription: jd })
        : await api.analyzeText({ resumeText, jobDescription: jd });
      toast.success('Analysis complete and saved.');
      navigate(`/results/${result.id}`, { state: { analysis: result } });
    } catch (err) {
      setServerError(err.message);
      if (err.details && typeof err.details === 'object') {
        setErrors((prev) => ({
          ...prev,
          resume: err.details.resume || prev.resume,
          jd: err.details.job_description || prev.jd,
        }));
      }
      toast.error(err.message);
      submitting.current = false;
      setLoading(false);
    }
  }

  return (
    <>
      <PageHeader title="New analysis" subtitle="Compare a resume with a job description to see an estimated compatibility score." />
      <form onSubmit={submit} noValidate>
        <div className="grid main-side" style={{ alignItems: 'start' }}>
          <div className="stack">
            <section className="card">
              <div className="card-head">
                <h2>1. Resume</h2>
                <div className="segmented" role="tablist" aria-label="Resume input method">
                  <button type="button" role="tab" aria-selected={mode === 'pdf'} className={mode === 'pdf' ? 'on' : ''} onClick={() => { setMode('pdf'); setErrors((x) => ({ ...x, resume: undefined })); }} disabled={loading}><Upload size={15} />Upload PDF</button>
                  <button type="button" role="tab" aria-selected={mode === 'text'} className={mode === 'text' ? 'on' : ''} onClick={() => { setMode('text'); setErrors((x) => ({ ...x, resume: undefined })); }} disabled={loading}><Type size={15} />Paste text</button>
                </div>
              </div>

              {mode === 'pdf' ? (
                <div className="field">
                  <input ref={inputRef} type="file" accept="application/pdf,.pdf" className="sr-only" tabIndex={-1}
                    onChange={(e) => { pickFile(e.target.files[0]); e.target.value = ''; }} />
                  {file ? (
                    <div className="file-row">
                      <div className="file-icon"><FileText size={19} /></div>
                      <div className="file-meta"><strong>{file.name}</strong><span className="muted small">{formatSize(file.size)} · PDF</span></div>
                      <button type="button" className="btn btn-secondary btn-sm" onClick={() => inputRef.current.click()} disabled={loading}>Replace</button>
                      <button type="button" className="btn btn-ghost btn-sm icon-btn" aria-label="Remove file" onClick={() => setFile(null)} disabled={loading}><X size={16} /></button>
                    </div>
                  ) : (
                    <div className={`dropzone ${dragOver ? 'over' : ''}`} role="button" tabIndex={0}
                      onClick={() => inputRef.current.click()}
                      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), inputRef.current.click())}
                      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                      onDragLeave={() => setDragOver(false)} onDrop={onDrop}>
                      <div className="dz-icon"><Upload size={22} /></div>
                      <strong>Drag and drop your resume here</strong>
                      <p className="muted small">or click to browse · PDF only · up to {MAX_MB} MB</p>
                    </div>
                  )}
                  {fileError && <span className="field-error">{fileError}</span>}
                  {errors.resume && !fileError && <span className="field-error">{errors.resume}</span>}
                  <p className="muted small">Text-based PDFs only. Scanned or image-only PDFs cannot be read.</p>
                </div>
              ) : (
                <div className="field">
                  <div className="label-row">
                    <label className="label" htmlFor="resume-text">Resume text</label>
                    <span className="counter">{resumeText.length.toLocaleString()} characters</span>
                  </div>
                  <textarea id="resume-text" className={`textarea ${errors.resume ? 'invalid' : ''}`} rows={12}
                    placeholder="Paste the full text of your resume…" value={resumeText} disabled={loading}
                    onChange={(e) => { setResumeText(e.target.value); setErrors((x) => ({ ...x, resume: undefined })); }} />
                  {errors.resume && <span className="field-error">{errors.resume}</span>}
                </div>
              )}
            </section>

            <section className="card">
              <div className="card-head"><h2>2. Job description</h2></div>
              <div className="field">
                <div className="label-row">
                  <label className="label" htmlFor="jd">Job description</label>
                  <span className="counter">{jd.length.toLocaleString()} characters</span>
                </div>
                <textarea id="jd" className={`textarea ${errors.jd ? 'invalid' : ''}`} rows={12}
                  placeholder="Paste the job description you are applying to…" value={jd} disabled={loading}
                  onChange={(e) => { setJd(e.target.value); setErrors((x) => ({ ...x, jd: undefined })); }} />
                {errors.jd && <span className="field-error">{errors.jd}</span>}
              </div>
            </section>
          </div>

          <aside className="stack">
            <section className="card">
              <h2 style={{ marginBottom: 10 }}>Run analysis</h2>
              <p className="muted small" style={{ marginBottom: 16 }}>
                The engine compares text similarity and the technical skills found in both documents, then saves the result to your history.
              </p>
              {serverError && (
                <div className="banner warn" role="alert" style={{ marginBottom: 16 }}>
                  <AlertTriangle size={18} /><div>{serverError}</div>
                </div>
              )}
              <button type="submit" className="btn btn-primary btn-lg" style={{ width: '100%' }} disabled={loading}>
                {loading ? <><Loader2 size={18} className="spin" />Analyzing…</> : <><Sparkles size={18} />Analyze resume</>}
              </button>
              {loading && <p className="muted small" style={{ marginTop: 12, textAlign: 'center' }}>Reading your documents. This usually takes a few seconds.</p>}
            </section>
            <section className="card">
              <h3 style={{ marginBottom: 8 }}>About the score</h3>
              <p className="muted small">
                The compatibility score is an estimate based on text similarity and skill coverage. It does not predict whether a real ATS will accept your resume.
              </p>
            </section>
          </aside>
        </div>
      </form>
    </>
  );
}
