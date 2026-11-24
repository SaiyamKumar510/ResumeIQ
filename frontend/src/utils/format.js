export function formatDate(iso, withTime = false) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString(
    undefined,
    withTime
      ? { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }
      : { year: 'numeric', month: 'short', day: 'numeric' },
  );
}

export function pct(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return `${Number(value).toFixed(digits).replace(/\.0+$/, '')}%`;
}

// Visual banding only (colour of rings/bars). It is not a hiring or ATS verdict.
export function scoreTone(score) {
  if (score === null || score === undefined) return 'neutral';
  if (score >= 70) return 'good';
  if (score >= 40) return 'mid';
  return 'low';
}

export function displayName(a) {
  return a.resume_filename || 'Pasted resume text';
}
