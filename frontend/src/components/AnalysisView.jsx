import { Check, ChevronRight, Info, Target, TriangleAlert, X } from 'lucide-react';
import { ProgressBar, ScoreRing } from './ui.jsx';
import { formatDate, pct } from '../utils/format.js';

function Metric({ label, value, hint }) {
  return (
    <div className="metric">
      <div className="metric-top"><span>{label}</span><span>{pct(value)}</span></div>
      {value === null || value === undefined ? <div className="bar" /> : <ProgressBar value={value} />}
      {hint && <div className="small muted">{hint}</div>}
    </div>
  );
}

function SkillChips({ items, kind, empty }) {
  if (!items || items.length === 0) return <p className="muted small">{empty}</p>;
  return (
    <div className="chips">
      {items.map((s) => (
        <span key={s} className={`chip ${kind}`}>
          {kind === 'good' ? <Check size={13} /> : <X size={13} />}{s}
        </span>
      ))}
    </div>
  );
}

export default function AnalysisView({ analysis: a }) {
  const categories = Object.entries(a.category_analysis || {});
  const keywords = a.extracted_keywords || [];
  const missingKw = a.missing_keywords || [];
  const notes = a.notes || [];
  const weights = a.weights || null;
  const matched = a.matched_skills || [];
  const missing = a.missing_skills || [];

  return (
    <div className="stack">
      <div className="banner" role="note">
        <Info size={18} />
        <div>
          <strong>This score is an estimate.</strong>{' '}
          {a.disclaimer ||
            'It is based on text similarity and technical-skill coverage and is not a guarantee of ATS acceptance.'}
        </div>
      </div>

      <section className="card hero">
        <ScoreRing score={a.overall_score} />
        <div className="hero-body">
          <div>
            <h2>Overall compatibility</h2>
            <p className="muted small">Analysed {formatDate(a.created_at, true)}</p>
          </div>
          <div className="grid cols-2">
            <Metric label="Text similarity" value={a.text_similarity} hint="TF-IDF cosine similarity of the two texts" />
            <Metric
              label="Skill coverage"
              value={a.skill_coverage}
              hint={
                a.skill_coverage === null || a.skill_coverage === undefined
                  ? 'No known skills were found in the job description'
                  : `${matched.length} of ${matched.length + missing.length} job skills found in the resume`
              }
            />
          </div>
        </div>
      </section>

      {notes.length > 0 && (
        <div className="banner warn" role="note">
          <TriangleAlert size={18} />
          <div>{notes.map((n, i) => <p key={i}>{n}</p>)}</div>
        </div>
      )}

      <div className="grid cols-2">
        <section className="card">
          <div className="card-head"><h2>Matched skills</h2><span className="chip good">{matched.length}</span></div>
          <SkillChips items={matched} kind="good" empty="No job-description skills were found in this resume." />
        </section>
        <section className="card">
          <div className="card-head"><h2>Missing skills</h2><span className="chip bad">{missing.length}</span></div>
          <SkillChips items={missing} kind="bad" empty="No missing skills. Every skill detected in the job description appears in the resume." />
        </section>
      </div>

      {categories.length > 0 && (
        <section className="card">
          <div className="card-head"><h2>Skill coverage by category</h2><Target size={18} className="muted" /></div>
          {categories.map(([name, c]) => (
            <div className="cat" key={name}>
              <div className="cat-top">
                <span>{name}</span>
                <span className="muted">{c.matched.length}/{c.required} · {pct(c.coverage)}</span>
              </div>
              <ProgressBar value={c.coverage} />
              <div className="chips">
                {c.matched.map((s) => <span key={`m-${s}`} className="chip good">{s}</span>)}
                {c.missing.map((s) => <span key={`x-${s}`} className="chip bad">{s}</span>)}
              </div>
            </div>
          ))}
        </section>
      )}

      <div className="grid cols-2">
        <section className="card">
          <div className="card-head"><h2>Extracted keywords</h2><span className="chip">{keywords.length}</span></div>
          {keywords.length === 0 ? (
            <p className="muted small">No keywords were extracted from the job description.</p>
          ) : (
            <div className="chips">
              {keywords.map((k) => (
                <span key={k.keyword} className={`chip ${k.is_skill ? 'accent' : ''}`} title={k.is_skill ? 'Recognised skill' : 'Keyword'}>
                  {k.keyword}{k.count > 1 && <small>×{k.count}</small>}
                </span>
              ))}
            </div>
          )}
          <p className="muted small" style={{ marginTop: 12 }}>Highlighted keywords are recognised skills.</p>
        </section>
        <section className="card">
          <div className="card-head"><h2>Missing keywords</h2><span className="chip bad">{missingKw.length}</span></div>
          <SkillChips items={missingKw} kind="bad" empty="No important job-description keywords are missing from the resume." />
        </section>
      </div>

      <section className="card">
        <h2 style={{ marginBottom: 12 }}>How the score is calculated</h2>
        <p>{a.scoring_explanation}</p>
        {weights && (
          <p className="muted small" style={{ marginTop: 10 }}>
            Weights used: {Math.round((weights.similarity ?? 0) * 100)}% text similarity, {Math.round((weights.skills ?? 0) * 100)}% skill coverage.
            These weights are a fixed, hand-chosen setting and have not been validated against real ATS outcomes.
          </p>
        )}
      </section>

      {(a.resume_text || a.job_description) && (
        <section className="card">
          <h2 style={{ marginBottom: 6 }}>Analysed text</h2>
          {a.resume_text && (
            <details className="disclose">
              <summary><ChevronRight size={16} />Resume{a.resume_filename ? ` · ${a.resume_filename}` : ''}</summary>
              <div className="pre">{a.resume_text}</div>
            </details>
          )}
          {a.job_description && (
            <details className="disclose">
              <summary><ChevronRight size={16} />Job description</summary>
              <div className="pre">{a.job_description}</div>
            </details>
          )}
        </section>
      )}
    </div>
  );
}

