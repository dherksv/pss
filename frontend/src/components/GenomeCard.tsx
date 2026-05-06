import { api } from '../lib/api';

const SOURCE_ICONS: Record<string, string> = {
  reddit: '👾', twitter: '🐦', forum: '💬', rss: '📰',
};

const TYPE_PILL: Record<string, string> = {
  adverse_drug_reaction:    'pill-adr',
  distress:                 'pill-distress',
  misinformation:           'pill-misinfo',
  treatment_dissatisfaction:'pill-review',
  general:                  'pill-general',
};

function ago(ts: string) {
  const d = Date.now() - new Date(ts).getTime();
  if (d < 60000)   return `${Math.floor(d/1000)}s ago`;
  if (d < 3600000) return `${Math.floor(d/60000)}m ago`;
  return `${Math.floor(d/3600000)}h ago`;
}

function pct(n: number) { return `${(n * 100).toFixed(0)}%`; }

// ── Compact card for feed list ─────────────────────────────
export function GenomeCard({ g, selected, onClick }: {
  g: any; selected?: boolean; onClick?: () => void;
}) {
  const typeClass = TYPE_PILL[g.signal_type] || 'pill-general';
  const typeLabel = (g.signal_type || 'general').replace(/_/g, ' ');

  return (
    <div className={`genome-card ${selected ? 'selected' : ''}`} onClick={onClick}>
      <div className="genome-top">
        <span className="genome-source">
          {SOURCE_ICONS[g.source_type] || '📡'} {g.source}
        </span>
        <div style={{ display:'flex', gap:6, alignItems:'center' }}>
          <span className={`pill ${typeClass}`}>{typeLabel}</span>
          <span className="genome-time">{ago(g.created_at)}</span>
        </div>
      </div>

      <div className="genome-text">{g.raw_text || g.pii_redacted_text}</div>

      <div className="genome-footer">
        {g.entities?.drugs?.slice(0,2).map((d: string) => (
          <span key={d} className="entity-chip">{d}</span>
        ))}
        {g.entities?.symptoms?.slice(0,2).map((s: string) => (
          <span key={s} className="entity-chip symptom">{s}</span>
        ))}

        {/* Open original thread */}
        {g.source_url && (
          <a href={g.source_url} target="_blank" rel="noopener noreferrer"
            onClick={e => e.stopPropagation()}
            className="entity-chip"
            style={{ color:'var(--accent)', textDecoration:'none', marginLeft:'auto',
                     background:'rgba(61,142,240,0.08)' }}>
            {SOURCE_ICONS[g.source_type] || '🔗'} thread ↗
          </a>
        )}

        <div className="score-bar-wrap">
          <span className="score-label">novelty</span>
          <div className="score-bar">
            <div className="score-fill danger" style={{ width: pct(g.novelty?.score || 0) }}/>
          </div>
          <span className="score-val">{pct(g.novelty?.score || 0)}</span>
        </div>
        <div className="score-bar-wrap">
          <span className="score-label">conf</span>
          <div className="score-bar">
            <div className="score-fill" style={{ width: pct(g.confidence_score || 0) }}/>
          </div>
          <span className="score-val">{pct(g.confidence_score || 0)}</span>
        </div>
      </div>
    </div>
  );
}

// ── Full genome detail pane ────────────────────────────────
export function GenomeDetail({ g }: { g: any }) {
  const typeClass = TYPE_PILL[g.signal_type] || 'pill-general';

  return (
    <div className="genome-detail">
      <div className="panel-hdr">
        <div>
          <div className="panel-kicker">Signal Genome</div>
          <div className="panel-title" style={{ fontSize:11, fontFamily:'var(--mono)' }}>
            {g.genome_id?.slice(0,20)}…
          </div>
        </div>
        <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
          <span className={`pill ${typeClass}`}>
            {(g.signal_type || 'general').replace(/_/g,' ')}
          </span>
          {g.source_url && (
            <a href={g.source_url} target="_blank" rel="noopener noreferrer"
              className="p-btn"
              style={{ textDecoration:'none', display:'inline-flex', alignItems:'center', gap:4 }}>
              {SOURCE_ICONS[g.source_type] || '🔗'} View Source ↗
            </a>
          )}
        </div>
      </div>

      {/* Original text */}
      <div className="detail-section" style={{ borderLeft:'3px solid var(--border)' }}>
        <div className="detail-section-title">Original Post</div>
        <div style={{ fontSize:12, lineHeight:1.6 }}>{g.raw_text || g.pii_redacted_text}</div>
        {g.source_url && (
          <a href={g.source_url} target="_blank" rel="noopener noreferrer"
            style={{ marginTop:8, display:'inline-flex', alignItems:'center', gap:4,
                     fontFamily:'var(--mono)', fontSize:9, color:'var(--accent)', textDecoration:'none' }}>
            {SOURCE_ICONS[g.source_type] || '🔗'} Open on {g.source_type} ↗
          </a>
        )}
      </div>

      {/* Source */}
      <div className="detail-section">
        <div className="detail-section-title">Source</div>
        <div className="detail-row"><span className="detail-key">Platform</span><span className="detail-val">{g.source}</span></div>
        <div className="detail-row"><span className="detail-key">Type</span><span className="detail-val">{g.source_type}</span></div>
        <div className="detail-row"><span className="detail-key">Timestamp</span><span className="detail-val">{ago(g.created_at)}</span></div>
      </div>

      {/* Entities */}
      <div className="detail-section">
        <div className="detail-section-title">Entities Detected</div>
        <div style={{ marginBottom:6 }}>
          <div className="detail-key" style={{ fontSize:10, marginBottom:4 }}>Drugs</div>
          <div className="entity-chips">
            {g.entities?.drugs?.map((d: string) => <span key={d} className="entity-chip">{d}</span>)}
          </div>
        </div>
        <div style={{ marginBottom:6 }}>
          <div className="detail-key" style={{ fontSize:10, marginBottom:4 }}>Symptoms</div>
          <div className="entity-chips">
            {g.entities?.symptoms?.map((s: string) => <span key={s} className="entity-chip symptom">{s}</span>)}
          </div>
        </div>
        <div>
          <div className="detail-key" style={{ fontSize:10, marginBottom:4 }}>Locations</div>
          <div className="entity-chips">
            {g.entities?.locations?.map((l: string) => <span key={l} className="entity-chip location">{l}</span>)}
          </div>
        </div>
      </div>

      {/* Scores */}
      <div className="detail-section">
        <div className="detail-section-title">Scores</div>
        <div className="detail-row">
          <span className="detail-key">Sentiment</span>
          <span className="detail-val"
            style={{ color: (g.sentiment_score||0) < -0.3 ? 'var(--danger)' : 'var(--success)' }}>
            {((g.sentiment_score||0)*100).toFixed(0)}%
          </span>
        </div>
        <div className="detail-row">
          <span className="detail-key">Confidence</span>
          <span className="detail-val">{pct(g.confidence_score||0)}</span>
        </div>
        <div className="detail-row">
          <span className="detail-key">Novelty Score</span>
          <span className="detail-val"
            style={{ color: (g.novelty?.score||0) > 0.7 ? 'var(--danger)' : 'var(--text)' }}>
            {pct(g.novelty?.score||0)}
          </span>
        </div>
        <div className="detail-row">
          <span className="detail-key">In FDA Label</span>
          <span className="detail-val"
            style={{ color: g.novelty?.in_fda_label ? 'var(--success)' : 'var(--danger)' }}>
            {g.novelty?.in_fda_label ? '✓ Documented' : '✗ Not documented'}
          </span>
        </div>
        <div className="detail-row">
          <span className="detail-key">FAERS Reports</span>
          <span className="detail-val">{g.novelty?.faers_count ?? '—'}</span>
        </div>
      </div>

      {/* PII warning */}
      {g.pii_detected && (
        <div className="detail-section" style={{ borderColor:'rgba(240,160,48,0.3)' }}>
          <div className="detail-section-title">⚠ PII/PHI Detected</div>
          <div style={{ fontSize:11, color:'var(--warning)' }}>
            Personal information was detected and redacted before processing.
          </div>
        </div>
      )}

      {/* XAI */}
      <div className="panel-kicker" style={{ marginBottom:4 }}>XAI Explanation</div>
      <div className="explanation-box">{g.explanation || 'No explanation generated.'}</div>
    </div>
  );
}