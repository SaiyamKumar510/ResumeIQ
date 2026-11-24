import { useEffect } from 'react';
import { AlertTriangle, Loader2, RefreshCw } from 'lucide-react';
import { pct, scoreTone } from '../utils/format.js';

export function PageHeader({ title, subtitle, children }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {children && <div className="head-actions">{children}</div>}
    </div>
  );
}

export function StatCard({ label, value, sub, icon: Icon }) {
  return (
    <div className="card stat">
      <div className="stat-top">
        <span>{label}</span>
        {Icon && <span className="stat-icon"><Icon size={17} /></span>}
      </div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

export function ProgressBar({ value, tone }) {
  const v = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div className={`bar ${tone || scoreTone(v)}`} role="progressbar" aria-valuenow={v} aria-valuemin={0} aria-valuemax={100}>
      <i style={{ width: `${v}%` }} />
    </div>
  );
}

export function ScoreRing({ score, size = 168, stroke = 13 }) {
  const v = Math.max(0, Math.min(100, Number(score) || 0));
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  return (
    <div className={`ring ${scoreTone(v)}`} style={{ width: size, height: size }}>
      <svg width={size} height={size} aria-hidden="true">
        <circle className="ring-track" cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke} />
        <circle
          className="ring-val" cx={size / 2} cy={size / 2} r={r} fill="none" strokeWidth={stroke}
          strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - v / 100)}
        />
      </svg>
      <div className="ring-center" role="img" aria-label={`Compatibility score ${pct(v)}`}>
        <b>{pct(v)}</b>
        <span>Estimated match</span>
      </div>
    </div>
  );
}

export function Skeleton({ height = 16, width = '100%', style }) {
  return <div className="skel" style={{ height, width, ...style }} />;
}

export function EmptyState({ icon: Icon, title, text, children }) {
  return (
    <div className="state">
      {Icon && <div className="state-icon"><Icon size={26} /></div>}
      <h2>{title}</h2>
      {text && <p>{text}</p>}
      {children && <div className="head-actions">{children}</div>}
    </div>
  );
}

export function ErrorState({ title = 'Something went wrong', message, onRetry, children }) {
  return (
    <div className="state error">
      <div className="state-icon"><AlertTriangle size={26} /></div>
      <h2>{title}</h2>
      <p>{message}</p>
      <div className="head-actions">
        {onRetry && (
          <button className="btn btn-secondary" onClick={onRetry}><RefreshCw size={16} />Try again</button>
        )}
        {children}
      </div>
    </div>
  );
}

export function ConfirmModal({ open, title, message, confirmLabel = 'Confirm', busy, onConfirm, onCancel }) {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => e.key === 'Escape' && !busy && onCancel();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, busy, onCancel]);

  if (!open) return null;
  return (
    <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && !busy && onCancel()}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
        <h2 id="modal-title">{title}</h2>
        <p>{message}</p>
        <div className="actions">
          <button className="btn btn-secondary" onClick={onCancel} disabled={busy}>Cancel</button>
          <button className="btn btn-danger" onClick={onConfirm} disabled={busy} autoFocus>
            {busy && <Loader2 size={16} className="spin" />}{confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
