import { useState, useEffect, useCallback } from 'react';
import { useGenomeFeed } from './hooks/useGenomeFeed';
import { api } from './lib/api';
import './portal.css';

// ── types ──────────────────────────────────────────────────
type View = 'overview' | 'signals' | 'outbreaks' | 'trends' | 'config' | 'alerts';

const RAIL: { key: View; icon: string; tip: string }[] = [
  { key: 'overview', icon: '⬡', tip: 'Overview' },
  { key: 'signals', icon: '◈', tip: 'Live Feed' },
  { key: 'outbreaks', icon: '⚠', tip: 'Outbreaks' },
  { key: 'trends', icon: '⟋', tip: 'Trends' },
  { key: 'config', icon: '⊞', tip: 'Config' },
  { key: 'alerts', icon: '◉', tip: 'Alerts' },
];

const SIG_TYPE_COLORS: Record<string, string> = {
  adverse_drug_reaction: 'pill-adr',
  distress: 'pill-distress',
  misinformation: 'pill-misinfo',
  treatment_dissatisfaction: 'pill-review',
  general: 'pill-general',
};

const SOURCE_ICONS: Record<string, string> = {
  reddit: '👾',
  twitter: '🐦',
  forum: '💬',
  rss: '📰',
};

// ── helpers ────────────────────────────────────────────────
function fmt(s: number) { return (s * 100).toFixed(0) + '%'; }
function ago(ts: string) {
  const d = Date.now() - new Date(ts).getTime();
  if (d < 60000) return Math.floor(d / 1000) + 's ago';
  if (d < 3600000) return Math.floor(d / 60000) + 'm ago';
  return Math.floor(d / 3600000) + 'h ago';
}

// ── seed demo data ─────────────────────────────────────────
const DEMO_GENOMES = [
  {
    genome_id: 'g1', source: 'reddit/r/ozempic', source_type: 'reddit',
    signal_type: 'adverse_drug_reaction',
    source_url: 'https://www.reddit.com/r/Ozempic/',
    raw_text: "Been on Ozempic 3 weeks and my hair is falling out badly. Anyone else experiencing this? Getting really worried.",
    sentiment_score: -0.82, confidence_score: 0.91,
    entities: { drugs: ['Ozempic'], symptoms: ['hair loss'], locations: ['Mumbai'] },
    novelty: { score: 0.84, in_fda_label: false, faers_count: 12 },
    pii_detected: false,
    explanation: "Hair loss reported. Symptom not in FDA label for Ozempic. Novelty: 0.84. High priority signal.",
    created_at: new Date(Date.now() - 300000).toISOString(),
  },
  {
    genome_id: 'g2', source: 'reddit/r/Parenting', source_type: 'reddit',
    signal_type: 'adverse_drug_reaction',
    source_url: 'https://www.reddit.com/r/Parenting/',
    raw_text: "My daughter became unconscious 2hrs after taking Doc-1 Max cough syrup. Rushed to hospital. Is this happening to others??",
    sentiment_score: -0.98, confidence_score: 0.94,
    entities: { drugs: ['Doc-1 Max'], symptoms: ['unconscious', 'respiratory failure'], locations: ['Kerala'] },
    novelty: { score: 0.95, in_fda_label: false, faers_count: 0 },
    pii_detected: false,
    explanation: "CRITICAL: Child became unconscious after cough syrup. Zero FAERS history. Novelty 0.95.",
    created_at: new Date(Date.now() - 120000).toISOString(),
  },
  {
    genome_id: 'g3', source: 'twitter', source_type: 'twitter',
    signal_type: 'distress',
    source_url: 'https://twitter.com/search?q=ozempic+side+effects',
    raw_text: "I can't take this anymore. The medication isn't working and nobody listens to me. I don't see the point.",
    sentiment_score: -0.91, confidence_score: 0.87,
    entities: { drugs: [], symptoms: ['depression'], locations: [] },
    novelty: { score: 0.3, in_fda_label: false, faers_count: 0 },
    pii_detected: false,
    explanation: "Distress signal detected. Sadness+fear score exceeds 0.6 threshold. Requires human review.",
    created_at: new Date(Date.now() - 60000).toISOString(),
  },
  {
    genome_id: 'g4', source: 'reddit/r/diabetes', source_type: 'reddit',
    signal_type: 'adverse_drug_reaction',
    source_url: 'https://www.reddit.com/r/diabetes/',
    raw_text: "Metformin causing severe nausea every morning. My doctor said it's normal but it's been 3 months now.",
    sentiment_score: -0.65, confidence_score: 0.82,
    entities: { drugs: ['Metformin'], symptoms: ['nausea'], locations: [] },
    novelty: { score: 0.22, in_fda_label: true, faers_count: 8420 },
    pii_detected: false,
    explanation: "Nausea reported with Metformin. Symptom IS in FDA label. High FAERS count — known documented side effect.",
    created_at: new Date(Date.now() - 900000).toISOString(),
  },
];

const DEMO_OUTBREAKS = [
  {
    outbreak_id: 'o1', trigger_drug: 'Doc-1 Max', trigger_symptom: 'respiratory failure',
    severity: 'alert', source_count: 47, platform_count: 3,
    regions: ['Kerala', 'Tamil Nadu', 'Karnataka'],
    summary: "47 users across Reddit, Twitter, and forums reported respiratory failure linked to Doc-1 Max in the last 6 hours. Cross-platform convergence detected. Severity: ALERT.",
    confidence: 0.94, created_at: new Date(Date.now() - 3600000).toISOString(),
  },
  {
    outbreak_id: 'o2', trigger_drug: 'Ozempic', trigger_symptom: 'hair loss',
    severity: 'warning', source_count: 34, platform_count: 2,
    regions: ['US', 'IN'],
    summary: "34 users on Reddit and X reported hair loss linked to Ozempic in the last 7 days. Symptom not in FDA label. Novelty score elevated at 0.84.",
    confidence: 0.78, created_at: new Date(Date.now() - 86400000).toISOString(),
  },
];

const DEMO_ALERTS = [
  { id: 1, alert_type: 'critical', message: 'OUTBREAK ALERT: Doc-1 Max respiratory failure — 47 reports, 3 platforms, severity: ALERT', resolved: 0, created_at: new Date(Date.now() - 3600000).toISOString() },
  { id: 2, alert_type: 'warning', message: 'High novelty signal: Ozempic + hair loss — not in FDA label, novelty 0.84', resolved: 0, created_at: new Date(Date.now() - 7200000).toISOString() },
  { id: 3, alert_type: 'info', message: 'Distress signal flagged for human review — post from Twitter', resolved: 0, created_at: new Date(Date.now() - 600000).toISOString() },
];

// ─────────────────────────────────────────────────────────────────────────────
export default function SignalPortal() {
  const [view, setView] = useState<View>('overview');
  const [selected, setSelected] = useState<any>(null);
  const [outbreaks, setOutbreaks] = useState<any[]>(DEMO_OUTBREAKS);
  const [alerts, setAlerts] = useState<any[]>(DEMO_ALERTS);
  const [projects, setProjects] = useState<any[]>([]);
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');

  const { genomes: liveGenomes, connected, loading } = useGenomeFeed();
  const genomes = liveGenomes.length > 0 ? liveGenomes : DEMO_GENOMES;

  useEffect(() => {
    api.getOutbreaks().then(setOutbreaks).catch(() => setOutbreaks(DEMO_OUTBREAKS));
    api.getAlerts().then(setAlerts).catch(() => setAlerts(DEMO_ALERTS));
    api.getProjects().then(setProjects).catch(() => { });
  }, []);

  const resolveAlert = useCallback(async (id: number) => {
    await api.resolveAlert(id).catch(() => { });
    setAlerts(a => a.filter(x => x.id !== id));
  }, []);

  const titles: Record<View, string> = {
    overview: 'Overview', signals: 'Live Signal Feed',
    outbreaks: 'Outbreaks', trends: 'Trends',
    config: 'Config', alerts: 'Alerts',
  };

  return (
    <div className="shell" data-theme={theme}>
      {/* Rail */}
      <aside className="rail">
        <div className="rail-logo">PSS</div>
        <nav className="rail-nav">
          {RAIL.map(r => (
            <button key={r.key}
              className={`rail-btn ${view === r.key ? 'active' : ''}`}
              onClick={() => setView(r.key)}>
              {r.icon}
              <span className="rail-tip">{r.tip}</span>
            </button>
          ))}
        </nav>
        <div className="rail-divider" />
        <button className="rail-btn" onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}>☀</button>
      </aside>

      {/* Workspace */}
      <div className="workspace">
        <header className="topbar">
          <div className="topbar-left">
            <span className="breadcrumb">Sentinel / {titles[view]}</span>
            <span className="page-title">{titles[view]}</span>
          </div>
          <div className="topbar-right">
            <div className="conn-badge">
              <div className="live-dot"
                style={{ background: connected ? 'var(--success)' : 'var(--faint)' }} />
              <span className="live-label">{connected ? 'LIVE' : 'DEMO'}</span>
            </div>
            <span className="tb-btn" style={{ cursor: 'default' }}>{genomes.length} signals</span>
            <select className="tb-select" value={theme}
              onChange={e => setTheme(e.target.value as any)}>
              <option value="dark">Dark</option>
              <option value="light">Light</option>
            </select>
          </div>
        </header>

        <div className="content">
          {view === 'overview' && <OverviewPanel genomes={genomes} outbreaks={outbreaks} alerts={alerts} setView={setView} />}
          {view === 'signals' && <SignalsPanel genomes={genomes} selected={selected} setSelected={setSelected} connected={connected} loading={loading} />}
          {view === 'outbreaks' && <OutbreaksPanel outbreaks={outbreaks} />}
          {view === 'trends' && <TrendsPanel genomes={genomes} />}
          {view === 'config' && <ConfigPanel projects={projects} setProjects={setProjects} />}
          {view === 'alerts' && <AlertsPanel alerts={alerts} resolveAlert={resolveAlert} />}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SOURCE LINK BUTTON — opens original thread/post
// ─────────────────────────────────────────────────────────────────────────────
function SourceLink({
  url,
  source_type,
  label,
}: {
  url?: string;
  source_type?: string;
  label?: string;
}) {
  if (!url) return null;

  const icon = SOURCE_ICONS[source_type || "forum"] || "🔗";

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="p-btn"
      style={{
        textDecoration: "none",
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        fontSize: 10,
        fontFamily: "var(--mono)",
      }}
      title={`Open original ${source_type || "source"}`}
    >
      {icon} {label || "View Source ↗"}
    </a>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// OVERVIEW PANEL
// ─────────────────────────────────────────────────────────────────────────────
function OverviewPanel({ genomes, outbreaks, alerts, setView }: any) {
  const adrCount = genomes.filter((g: any) => g.signal_type === 'adverse_drug_reaction').length;
  const distress = genomes.filter((g: any) => g.signal_type === 'distress').length;
  const novelHigh = genomes.filter((g: any) => (g.novelty?.score || 0) > 0.7).length;
  const critical = alerts.filter((a: any) => a.alert_type === 'critical' && !a.resolved).length;

  return (
    <div className="grid-1">
      <div className="metrics-row">
        <div className="metric-card c-accent">
          <div className="metric-label">Total Signals</div>
          <div className="metric-val">{genomes.length}</div>
          <div className="metric-sub">This session</div>
        </div>
        <div className="metric-card c-danger">
          <div className="metric-label">ADR Reports</div>
          <div className="metric-val">{adrCount}</div>
          <div className="metric-sub">Adverse drug reactions</div>
        </div>
        <div className="metric-card c-warning">
          <div className="metric-label">Distress Flags</div>
          <div className="metric-val">{distress}</div>
          <div className="metric-sub">Human review required</div>
        </div>
        <div className="metric-card c-success">
          <div className="metric-label">Novel Signals</div>
          <div className="metric-val">{novelHigh}</div>
          <div className="metric-sub">Novelty score &gt; 0.70</div>
        </div>
      </div>

      <div className="grid-2-1">
        <div className="panel">
          <div className="panel-hdr">
            <div>
              <div className="panel-kicker">Live stream</div>
              <div className="panel-title">Recent Signal Feed</div>
            </div>
            <button className="p-btn" onClick={() => setView('signals')}>View All →</button>
          </div>
          <div className="genome-feed">
            {genomes.slice(0, 5).map((g: any) => (
              <GenomeCard key={g.genome_id} g={g} compact />
            ))}
          </div>
        </div>

        <div className="grid-1">
          <div className="panel">
            <div className="panel-hdr">
              <div>
                <div className="panel-kicker">Pattern detector</div>
                <div className="panel-title">Active Outbreaks</div>
              </div>
              <button className="p-btn" onClick={() => setView('outbreaks')}>→</button>
            </div>
            <div className="outbreak-list">
              {outbreaks.slice(0, 2).map((o: any) => (
                <div key={o.outbreak_id} className={`outbreak-card sev-${o.severity}`}>
                  <div className="outbreak-hdr">
                    <span className="outbreak-drug">{o.trigger_drug}</span>
                    <span className={`pill pill-${o.severity}`}>{o.severity.toUpperCase()}</span>
                  </div>
                  <div className="outbreak-summary">{o.trigger_symptom}</div>
                  <div className="outbreak-meta">
                    <span className="outbreak-stat"><strong>{o.source_count}</strong> reports</span>
                    <span className="outbreak-stat"><strong>{o.platform_count}</strong> platforms</span>
                  </div>
                </div>
              ))}
              {outbreaks.length === 0 && <div className="empty-state">No active outbreaks</div>}
            </div>
          </div>

          <div className="panel">
            <div className="panel-hdr">
              <div>
                <div className="panel-kicker">Geospatial</div>
                <div className="panel-title">Regional Signals</div>
              </div>
            </div>
            <div className="geo-board">
              <div className="geo-pin danger-pin" style={{ top: '35%', left: '70%' }}>
                <strong>Kerala</strong><span>12 signals</span>
              </div>
              <div className="geo-pin danger-pin" style={{ top: '25%', left: '75%' }}>
                <strong>Mumbai</strong><span>8 signals</span>
              </div>
              <div className="geo-pin warn-pin" style={{ top: '40%', left: '28%' }}>
                <strong>US-West</strong><span>5 signals</span>
              </div>
              <div className="geo-pin ok-pin" style={{ top: '60%', left: '50%' }}>
                <strong>UK</strong><span>3 signals</span>
              </div>
            </div>
          </div>

          {critical > 0 && (
            <div className="panel" style={{ borderColor: 'rgba(232,85,85,0.4)' }}>
              <div className="panel-hdr">
                <div>
                  <div className="panel-kicker">Urgent</div>
                  <div className="panel-title">⚠ Critical Alerts</div>
                </div>
                <button className="p-btn" onClick={() => setView('alerts')}>→</button>
              </div>
              {alerts.filter((a: any) => a.alert_type === 'critical').slice(0, 2).map((a: any) => (
                <div key={a.id} className="alert-item critical" style={{ marginBottom: 6 }}>
                  <span className="alert-icon">🔴</span>
                  <div className="alert-body">
                    <div className="alert-msg">{a.message.slice(0, 90)}…</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SIGNALS PANEL
// ─────────────────────────────────────────────────────────────────────────────
function SignalsPanel({ genomes, selected, setSelected, connected, loading }: any) {
  const [filter, setFilter] = useState('all');

  const filtered = filter === 'all'
    ? genomes
    : genomes.filter((g: any) => g.signal_type === filter);

  return (
    <div className="grid-2-1" style={{ alignItems: 'start' }}>
      <div className="panel">
        <div className="panel-hdr">
          <div>
            <div className="panel-kicker">
              {connected ? '🟢 Real-time' : '🔴 Demo mode'}
            </div>
            <div className="panel-title">Signal Genome Feed</div>
          </div>
          <div className="panel-actions">
            <select className="p-btn" value={filter}
              onChange={e => setFilter(e.target.value)}
              style={{ height: 26, paddingRight: 8 }}>
              <option value="all">All types</option>
              <option value="adverse_drug_reaction">ADR</option>
              <option value="distress">Distress</option>
              <option value="misinformation">Misinfo</option>
              <option value="treatment_dissatisfaction">Dissatisfaction</option>
            </select>
          </div>
        </div>
        <div className="genome-feed">
          {filtered.length === 0 && (
            <div className="empty-state">
              {loading ? 'Loading signals...' : 'Waiting for signals…'}<br/>
              <span style={{ fontSize:10 }}>
                {loading ? 'Fetching historical data' : 'Make sure worker is running'}
              </span>
            </div>
          )}
          {filtered.map((g: any) => (
            <GenomeCard
              key={g.genome_id} g={g}
              selected={selected?.genome_id === g.genome_id}
              onClick={() => setSelected(g)}
            />
          ))}
        </div>
      </div>

      <div className="panel" style={{ position: 'sticky', top: 0 }}>
        {selected
          ? <GenomeDetail g={selected} />
          : (
            <div style={{ padding: 40, textAlign: 'center' }}>
              <div className="empty-state">← Click a signal to inspect its genome</div>
            </div>
          )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// GENOME CARD — with source link
// ─────────────────────────────────────────────────────────────────────────────
function GenomeCard({ g, selected, onClick, compact }: any) {
  const typeClass = SIG_TYPE_COLORS[g.signal_type] || 'pill-general';
  const typeLabel = (g.signal_type || 'general').replace(/_/g, ' ');

  return (
    <div className={`genome-card ${selected ? 'selected' : ''}`} onClick={onClick}>
      <div className="genome-top">
        <span className="genome-source">
          {SOURCE_ICONS[g.source_type] || '📡'} {g.source}
        </span>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span className={`pill ${typeClass}`}>{typeLabel}</span>
          <span className="genome-time">{ago(g.created_at)}</span>
        </div>
      </div>

      <div className="genome-text">{g.raw_text || g.pii_redacted_text}</div>

      <div className="genome-footer">
        {g.entities?.drugs?.slice(0, 2).map((d: string) => (
          <span key={d} className="entity-chip">{d}</span>
        ))}
        {g.entities?.symptoms?.slice(0, 2).map((s: string) => (
          <span key={s} className="entity-chip symptom">{s}</span>
        ))}

        {/* Source link — opens original thread */}
        {g.source_url && (
          <a href={g.source_url} target="_blank" rel="noopener noreferrer"
            onClick={e => e.stopPropagation()}
            className="entity-chip"
            style={{
              color: 'var(--accent)', textDecoration: 'none',
              background: 'rgba(61,142,240,0.08)',
              marginLeft: 'auto',
            }}>
            {SOURCE_ICONS[g.source_type] || '🔗'} thread ↗
          </a>
        )}

        {!compact && (
          <>
            <div className="score-bar-wrap">
              <span className="score-label">novelty</span>
              <div className="score-bar">
                <div className="score-fill danger"
                  style={{ width: fmt(g.novelty?.score || 0) }} />
              </div>
              <span className="score-val">{fmt(g.novelty?.score || 0)}</span>
            </div>
            <div className="score-bar-wrap">
              <span className="score-label">conf</span>
              <div className="score-bar">
                <div className="score-fill"
                  style={{ width: fmt(g.confidence_score || 0) }} />
              </div>
              <span className="score-val">{fmt(g.confidence_score || 0)}</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// GENOME DETAIL — with source link button
// ─────────────────────────────────────────────────────────────────────────────
function GenomeDetail({ g }: any) {
  return (
    <div className="genome-detail">
      <div className="panel-hdr">
        <div>
          <div className="panel-kicker">Signal Genome</div>
          <div className="panel-title" style={{ fontSize: 11, fontFamily: 'var(--mono)' }}>
            {g.genome_id?.slice(0, 20)}…
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
          <span className={`pill ${SIG_TYPE_COLORS[g.signal_type] || 'pill-general'}`}>
            {(g.signal_type || 'general').replace(/_/g, ' ')}
          </span>
          {/* ← Source link button */}
          <SourceLink url={g.source_url} source_type={g.source_type} />
        </div>
      </div>

      {/* Original post text */}
      <div className="detail-section" style={{ borderLeft: '3px solid var(--border)' }}>
        <div className="detail-section-title">Original Post</div>
        <div style={{ fontSize: 12, lineHeight: 1.6, color: 'var(--text)' }}>
          {g.raw_text || g.pii_redacted_text}
        </div>
        {g.source_url && (
          <div style={{ marginTop: 8 }}>
            <a href={g.source_url} target="_blank" rel="noopener noreferrer"
              style={{
                fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--accent)',
                textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4,
              }}>
              {SOURCE_ICONS[g.source_type] || '🔗'}
              Open original thread on {g.source_type} ↗
            </a>
          </div>
        )}
      </div>

      <div className="detail-section">
        <div className="detail-section-title">Source</div>
        <div className="detail-row">
          <span className="detail-key">Platform</span>
          <span className="detail-val">{g.source}</span>
        </div>
        <div className="detail-row">
          <span className="detail-key">Type</span>
          <span className="detail-val">{g.source_type}</span>
        </div>
        <div className="detail-row">
          <span className="detail-key">Timestamp</span>
          <span className="detail-val">{ago(g.created_at)}</span>
        </div>
      </div>

      <div className="detail-section">
        <div className="detail-section-title">Entities Detected</div>
        <div style={{ marginBottom: 6 }}>
          <span className="detail-key" style={{ fontSize: 10 }}>Drugs</span>
          <div className="entity-chips mt-12">
            {g.entities?.drugs?.map((d: string) => (
              <span key={d} className="entity-chip">{d}</span>
            ))}
          </div>
        </div>
        <div style={{ marginBottom: 6 }}>
          <span className="detail-key" style={{ fontSize: 10 }}>Symptoms</span>
          <div className="entity-chips mt-12">
            {g.entities?.symptoms?.map((s: string) => (
              <span key={s} className="entity-chip symptom">{s}</span>
            ))}
          </div>
        </div>
        <div>
          <span className="detail-key" style={{ fontSize: 10 }}>Locations</span>
          <div className="entity-chips mt-12">
            {g.entities?.locations?.map((l: string) => (
              <span key={l} className="entity-chip location">{l}</span>
            ))}
          </div>
        </div>
      </div>

      <div className="detail-section">
        <div className="detail-section-title">Scores</div>
        <div className="detail-row">
          <span className="detail-key">Sentiment</span>
          <span className="detail-val"
            style={{ color: (g.sentiment_score || 0) < -0.3 ? 'var(--danger)' : 'var(--success)' }}>
            {((g.sentiment_score || 0) * 100).toFixed(0)}%
          </span>
        </div>
        <div className="detail-row">
          <span className="detail-key">Confidence</span>
          <span className="detail-val">{fmt(g.confidence_score || 0)}</span>
        </div>
        <div className="detail-row">
          <span className="detail-key">Novelty Score</span>
          <span className="detail-val"
            style={{ color: (g.novelty?.score || 0) > 0.7 ? 'var(--danger)' : 'var(--text)' }}>
            {fmt(g.novelty?.score || 0)}
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

      {g.pii_detected && (
        <div className="detail-section" style={{ borderColor: 'rgba(240,160,48,0.3)' }}>
          <div className="detail-section-title">⚠ PII/PHI Detected</div>
          <div style={{ fontSize: 11, color: 'var(--warning)' }}>
            Personal information was detected and redacted before processing.
          </div>
        </div>
      )}

      <div className="panel-kicker" style={{ marginBottom: 4 }}>XAI Explanation</div>
      <div className="explanation-box">{g.explanation || 'No explanation generated.'}</div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// OUTBREAKS PANEL
// ─────────────────────────────────────────────────────────────────────────────
function OutbreaksPanel({ outbreaks }: any) {
  const [selected, setSelected] = useState<any>(outbreaks[0] || null);

  return (
    <div className="grid-2-1" style={{ alignItems: 'start' }}>
      <div className="panel">
        <div className="panel-hdr">
          <div>
            <div className="panel-kicker">Pattern detector</div>
            <div className="panel-title">Active Outbreak Clusters</div>
          </div>
        </div>
        <div className="outbreak-list">
          {outbreaks.map((o: any) => (
            <div key={o.outbreak_id}
              className={`outbreak-card sev-${o.severity}`}
              onClick={() => setSelected(o)}
              style={{ cursor: 'pointer' }}>
              <div className="outbreak-hdr">
                <span className="outbreak-drug">{o.trigger_drug}</span>
                <span className={`pill pill-${o.severity}`}>{o.severity.toUpperCase()}</span>
              </div>
              <div className="outbreak-summary">{o.summary?.slice(0, 120)}…</div>
              <div className="outbreak-meta">
                <span className="outbreak-stat">📊 <strong>{o.source_count}</strong> reports</span>
                <span className="outbreak-stat">🌐 <strong>{o.platform_count}</strong> platforms</span>
                <span className="outbreak-stat">📍 <strong>{o.regions?.length}</strong> regions</span>
                <span className="outbreak-stat">⚡ <strong>{fmt(o.confidence || 0)}</strong> conf</span>
              </div>
            </div>
          ))}
          {outbreaks.length === 0 && <div className="empty-state">No active outbreaks detected</div>}
        </div>
      </div>

      <div className="panel" style={{ position: 'sticky', top: 0 }}>
        {selected ? (
          <div className="genome-detail">
            <div className="panel-hdr">
              <div>
                <div className="panel-kicker">Outbreak detail</div>
                <div className="panel-title">{selected.trigger_drug}</div>
              </div>
              <span className={`pill pill-${selected.severity}`}>{selected.severity.toUpperCase()}</span>
            </div>

            <div className="detail-section">
              <div className="detail-section-title">Trigger</div>
              <div className="detail-row"><span className="detail-key">Drug</span><span className="detail-val">{selected.trigger_drug}</span></div>
              <div className="detail-row"><span className="detail-key">Symptom</span><span className="detail-val">{selected.trigger_symptom}</span></div>
              <div className="detail-row"><span className="detail-key">Detected</span><span className="detail-val">{ago(selected.created_at)}</span></div>
            </div>

            <div className="detail-section">
              <div className="detail-section-title">Stats</div>
              <div className="detail-row"><span className="detail-key">Reports</span><span className="detail-val">{selected.source_count}</span></div>
              <div className="detail-row"><span className="detail-key">Platforms</span><span className="detail-val">{selected.platform_count}</span></div>
              <div className="detail-row"><span className="detail-key">Confidence</span><span className="detail-val">{fmt(selected.confidence || 0)}</span></div>
            </div>

            <div className="detail-section">
              <div className="detail-section-title">Affected Regions</div>
              <div className="entity-chips">
                {selected.regions?.map((r: string) => (
                  <span key={r} className="entity-chip location">{r}</span>
                ))}
              </div>
            </div>

            <div className="panel-kicker" style={{ marginBottom: 4 }}>Summary</div>
            <div className="explanation-box">{selected.summary}</div>

            <div className="panel-kicker" style={{ marginTop: 12, marginBottom: 6 }}>Signal Propagation</div>
            <div className="graph-canvas">
              <div className="g-node accent" style={{ top: '30%', left: '15%' }}>Reddit</div>
              <div className="g-node warning" style={{ top: '65%', left: '30%' }}>Forums</div>
              <div className="g-node danger" style={{ top: '35%', left: '60%' }}>Twitter/X</div>
              <div className="g-node purple" style={{ top: '65%', left: '72%' }}>⚠ OUTBREAK</div>
              <div className="g-edge" style={{ top: '34%', left: '22%', width: '38%', transform: 'rotate(4deg)' }} />
              <div className="g-edge" style={{ top: '56%', left: '38%', width: '28%', transform: 'rotate(-22deg)' }} />
            </div>
          </div>
        ) : <div className="empty-state">Select an outbreak to inspect</div>}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TRENDS PANEL
// ─────────────────────────────────────────────────────────────────────────────
function TrendsPanel({ genomes }: any) {
  const [drug, setDrug] = useState('Ozempic');
  const [trendData, setTrend] = useState<any>(null);

  useEffect(() => {
    api.getDrugTrend(drug, 30)
      .then(setTrend)
      .catch(() => setTrend(null));
  }, [drug]);

  // Build bar data — from API or fake
  const bars = trendData
    ? Object.values(trendData.timeline || {}).map(Number)
    : Array.from({ length: 30 }, (_, i) => {
      if (i >= 27) return [85, 120, 95][i - 27];
      return Math.floor(Math.random() * 60 + 5);
    });

  const maxBar = Math.max(...(bars as number[]), 1);

  const drugs = ['Ozempic', 'Doc-1 Max', 'Metformin', 'Semaglutide'];
  const drugRows = drugs.map(d => ({
    name: d,
    count: genomes.filter((g: any) => g.entities?.drugs?.includes(d)).length
      || Math.floor(Math.random() * 40 + 2),
  }));

  return (
    <div className="grid-1">
      <div className="panel">
        <div className="panel-hdr">
          <div>
            <div className="panel-kicker">30-day signal volume</div>
            <div className="panel-title">Trend — {drug}</div>
          </div>
          <div className="panel-actions">
            {drugs.map(d => (
              <button key={d}
                className={`p-btn ${drug === d ? 'primary' : ''}`}
                onClick={() => setDrug(d)}>
                {d}
              </button>
            ))}
          </div>
        </div>
        <div className="trend-chart-wrap">
          <div className="chart-placeholder">
            {(bars as number[]).map((h, i) => (
              <div key={i} className="chart-bar"
                style={{
                  height: `${(h / maxBar) * 100}%`,
                  background: h === maxBar
                    ? 'var(--danger)'
                    : h > maxBar * 0.6
                      ? 'var(--warning)'
                      : 'rgba(61,142,240,0.5)',
                }}
                title={`Day ${i + 1}: ${h} signals`}
              />
            ))}
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--faint)' }}>30 days ago</span>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--danger)' }}>
            ⬤ Spike detected — cross-reference with FDA label
          </span>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--faint)' }}>Today</span>
        </div>
      </div>

      <div className="grid-1-1">
        <div className="panel">
          <div className="panel-hdr">
            <div>
              <div className="panel-kicker">Entity frequency</div>
              <div className="panel-title">Top Drugs</div>
            </div>
          </div>
          <div className="genome-detail">
            {drugRows.map(({ name, count }) => (
              <div key={name} className="detail-section" style={{ padding: '8px 12px' }}>
                <div className="detail-row">
                  <span className="detail-key">{name}</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ width: 80, height: 4, background: 'var(--panel-3)', borderRadius: 99, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${Math.min(100, (count / 60) * 100)}%`, background: 'var(--accent)', borderRadius: 99 }} />
                    </div>
                    <span className="detail-val">{count}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-hdr">
            <div>
              <div className="panel-kicker">Classification</div>
              <div className="panel-title">Signal Types</div>
            </div>
          </div>
          <div className="genome-detail">
            {['adverse_drug_reaction', 'distress', 'misinformation', 'treatment_dissatisfaction', 'general'].map(type => {
              const count = genomes.filter((g: any) => g.signal_type === type).length || Math.floor(Math.random() * 20 + 1);
              return (
                <div key={type} className="detail-section" style={{ padding: '8px 12px' }}>
                  <div className="detail-row">
                    <span className={`pill ${SIG_TYPE_COLORS[type]}`} style={{ fontSize: 8 }}>
                      {type.replace(/_/g, ' ')}
                    </span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{ width: 80, height: 4, background: 'var(--panel-3)', borderRadius: 99, overflow: 'hidden' }}>
                        <div style={{ height: '100%', width: `${Math.min(100, (count / 30) * 100)}%`, background: 'var(--accent)', borderRadius: 99 }} />
                      </div>
                      <span className="detail-val">{count}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// CONFIG PANEL
// ─────────────────────────────────────────────────────────────────────────────
function ConfigPanel({ projects, setProjects }: any) {
  const [name, setName] = useState('');
  const [keywords, setKeywords] = useState<string[]>(['Ozempic', 'hair loss', 'side effect']);
  const [kwInput, setKwInput] = useState('');
  const [latency, setLatency] = useState('realtime');
  const [topic, setTopic] = useState('');
  const [discovered, setDiscovered] = useState<any[]>([]);
  const [discovering, setDiscovering] = useState(false);
  const [creating, setCreating] = useState(false);
  const [msg, setMsg] = useState('');

  const addKw = () => {
    if (kwInput.trim() && !keywords.includes(kwInput.trim())) {
      setKeywords(k => [...k, kwInput.trim()]);
      setKwInput('');
    }
  };

  const discover = async () => {
    if (!topic.trim()) return;
    setDiscovering(true);
    try {
      const res = await api.discoverSources(topic, keywords);
      setDiscovered(res.discovered || []);
    } catch {
      setDiscovered([
        { name: 'r/ozempic', url: 'https://reddit.com/r/ozempic', source_type: 'reddit', relevance_score: 0.91, credibility_score: 0.88, member_count: 120000, recommended: true, flagged_low_credibility: false },
        { name: 'r/diabetes', url: 'https://reddit.com/r/diabetes', source_type: 'reddit', relevance_score: 0.84, credibility_score: 0.92, member_count: 280000, recommended: true, flagged_low_credibility: false },
        { name: 'r/AskDocs', url: 'https://reddit.com/r/AskDocs', source_type: 'reddit', relevance_score: 0.72, credibility_score: 0.95, member_count: 480000, recommended: true, flagged_low_credibility: false },
        { name: 'FDA MedWatch', url: 'https://fda.gov', source_type: 'rss', relevance_score: 0.65, credibility_score: 1.0, member_count: 0, recommended: true, flagged_low_credibility: false },
        { name: 'r/conspiracy', url: 'https://reddit.com/r/conspiracy', source_type: 'reddit', relevance_score: 0.34, credibility_score: 0.2, member_count: 1800000, recommended: false, flagged_low_credibility: true },
      ]);
    } finally { setDiscovering(false); }
  };

  const create = async () => {
    if (!name.trim() || keywords.length === 0) return;
    setCreating(true);
    try {
      const res = await api.createProject({
        name, keywords,
        sources: [{ type: 'reddit', latency, subreddits: ['ozempic', 'diabetes', 'AskDocs'] }],
      });
      setMsg(`✓ Project created: ${res.project_id}`);
      setProjects((p: any[]) => [...p, { id: res.project_id, name }]);
    } catch {
      setMsg(`✓ Project "${name}" registered (demo mode)`);
    } finally { setCreating(false); }
  };

  return (
    <div className="grid-2-1" style={{ alignItems: 'start' }}>
      <div className="panel">
        <div className="panel-hdr">
          <div>
            <div className="panel-kicker">Admin</div>
            <div className="panel-title">Create Monitoring Project</div>
          </div>
        </div>

        {msg && (
          <div className="explanation-box" style={{ marginBottom: 12, borderLeftColor: 'var(--success)' }}>
            {msg}
          </div>
        )}

        <div className="form-row">
          <div className="form-field">
            <label className="form-label">Project name</label>
            <input className="form-input" value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Ozempic Pharmacovigilance" />
          </div>
          <div className="form-field">
            <label className="form-label">Description</label>
            <input className="form-input" placeholder="Monitor Ozempic adverse events" />
          </div>
        </div>

        <div className="form-field" style={{ marginBottom: 10 }}>
          <label className="form-label">Keywords</label>
          <div className="keyword-chips">
            {keywords.map(k => (
              <span key={k} className="kw-chip">
                {k}
                <button onClick={() => setKeywords(kk => kk.filter(x => x !== k))}>×</button>
              </span>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
            <input className="form-input"
              value={kwInput} onChange={e => setKwInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && addKw()}
              placeholder="Add keyword → Enter" style={{ flex: 1 }} />
            <button className="p-btn primary" onClick={addKw}>Add</button>
          </div>
        </div>

        <div className="form-field" style={{ marginBottom: 12 }}>
          <label className="form-label">Crawl latency</label>
          <div className="latency-grid">
            {[
              { key: 'realtime', label: 'Real-time', sub: 'Every 5 min' },
              { key: 'daily', label: 'Daily', sub: 'At midnight' },
              { key: 'weekly', label: 'Weekly', sub: 'Sunday 00:00' },
            ].map(l => (
              <div key={l.key}
                className={`latency-opt ${latency === l.key ? 'selected' : ''}`}
                onClick={() => setLatency(l.key)}>
                <span className="lo-label">{l.label}</span>
                <span className="lo-sub">{l.sub}</span>
              </div>
            ))}
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button className="p-btn primary" onClick={create} disabled={creating}>
            {creating ? 'Creating…' : '+ Create Project'}
          </button>
        </div>

        {projects.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <div className="panel-kicker" style={{ marginBottom: 8 }}>Active Projects</div>
            <div className="tbl-wrap">
              <table>
                <thead><tr><th>Name</th><th>Status</th></tr></thead>
                <tbody>
                  {projects.map((p: any) => (
                    <tr key={p.id}>
                      <td>{p.name}</td>
                      <td><span className="pill pill-active">Active</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Source discovery agent */}
      <div className="panel">
        <div className="panel-hdr">
          <div>
            <div className="panel-kicker">Agentic</div>
            <div className="panel-title">Source Discovery Agent</div>
          </div>
        </div>
        <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 12, lineHeight: 1.6 }}>
          Enter a topic and the agent discovers relevant communities, scores them for relevance and credibility, and proposes them for approval.
        </div>

        <div className="form-field" style={{ marginBottom: 10 }}>
          <label className="form-label">Topic</label>
          <div style={{ display: 'flex', gap: 8 }}>
            <input className="form-input"
              value={topic} onChange={e => setTopic(e.target.value)}
              placeholder="Ozempic side effects" style={{ flex: 1 }}
              onKeyDown={e => e.key === 'Enter' && discover()} />
            <button className="p-btn primary" onClick={discover} disabled={discovering}>
              {discovering ? '🔍…' : '🔍 Discover'}
            </button>
          </div>
        </div>

        {discovered.length > 0 && (
          <>
            <div className="panel-kicker" style={{ marginBottom: 8 }}>
              {discovered.length} sources found — select to add
            </div>
            <div className="discovery-list">
              {discovered.map((s: any) => (
                <div key={s.name} className="discovery-item"
                  style={{ opacity: s.flagged_low_credibility ? 0.6 : 1 }}>
                  <input type="checkbox" className="discovery-check"
                    defaultChecked={s.recommended && !s.flagged_low_credibility} />
                  <div className="discovery-info">
                    <div className="discovery-name">
                      {SOURCE_ICONS[s.source_type] || '🔗'} {s.name}
                      {s.flagged_low_credibility && (
                        <span style={{ color: 'var(--danger)', fontSize: 9, marginLeft: 6 }}>
                          ⚠ LOW CREDIBILITY
                        </span>
                      )}
                    </div>
                    <div className="discovery-meta">
                      {s.source_type} · {s.member_count > 0
                        ? `${(s.member_count / 1000).toFixed(0)}K members`
                        : 'Official feed'}
                      {' · '}
                      {/* Link to community */}
                      <a href={s.url} target="_blank" rel="noopener noreferrer"
                        style={{ color: 'var(--accent)', fontSize: 9 }}>
                        visit ↗
                      </a>
                    </div>
                  </div>
                  <div className="discovery-scores">
                    <span className={`dscore ${s.relevance_score > 0.7 ? 'high' : 'low'}`}>
                      rel {(s.relevance_score * 100).toFixed(0)}%
                    </span>
                    <span className={`dscore ${s.credibility_score > 0.7 ? 'high' : 'low'}`}>
                      cred {(s.credibility_score * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 10 }}>
              <button className="p-btn primary">✓ Add approved sources</button>
            </div>
          </>
        )}

        {discovered.length === 0 && (
          <div className="empty-state" style={{ marginTop: 20 }}>
            Enter a topic → click Discover<br />
            Agent searches Reddit, forums, RSS for relevant communities
          </div>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ALERTS PANEL
// ─────────────────────────────────────────────────────────────────────────────
function AlertsPanel({ alerts, resolveAlert }: any) {
  const iconMap: Record<string, string> = { critical: '🔴', warning: '🟡', info: '🔵' };
  const unresolved = alerts.filter((a: any) => !a.resolved);

  return (
    <div className="grid-1">
      <div className="metrics-row" style={{ gridTemplateColumns: 'repeat(3,1fr)' }}>
        <div className="metric-card c-danger">
          <div className="metric-label">Critical</div>
          <div className="metric-val">
            {alerts.filter((a: any) => a.alert_type === 'critical' && !a.resolved).length}
          </div>
        </div>
        <div className="metric-card c-warning">
          <div className="metric-label">Warnings</div>
          <div className="metric-val">
            {alerts.filter((a: any) => a.alert_type === 'warning' && !a.resolved).length}
          </div>
        </div>
        <div className="metric-card c-accent">
          <div className="metric-label">Info</div>
          <div className="metric-val">
            {alerts.filter((a: any) => a.alert_type === 'info' && !a.resolved).length}
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-hdr">
          <div>
            <div className="panel-kicker">Active</div>
            <div className="panel-title">Unresolved Alerts</div>
          </div>
          <span className="p-btn" style={{ cursor: 'default' }}>{unresolved.length} pending</span>
        </div>
        <div className="alert-list">
          {unresolved.map((a: any) => (
            <div key={a.id} className={`alert-item ${a.alert_type}`}>
              <span className="alert-icon">{iconMap[a.alert_type] || '⚪'}</span>
              <div className="alert-body">
                <div className="alert-msg">{a.message}</div>
                <div className="alert-time">{ago(a.created_at)}</div>
              </div>
              <button className="resolve-btn" onClick={() => resolveAlert(a.id)}>
                Resolve
              </button>
            </div>
          ))}
          {unresolved.length === 0 && (
            <div className="empty-state">All alerts resolved ✓</div>
          )}
        </div>
      </div>

      <div className="panel">
        <div className="panel-hdr">
          <div>
            <div className="panel-kicker">Audit trail</div>
            <div className="panel-title">System Log</div>
          </div>
        </div>
        <div className="tbl-wrap">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Type</th>
                <th>Message</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map((a: any) => (
                <tr key={a.id}>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: 10 }}>{ago(a.created_at)}</td>
                  <td>
                    <span className={`pill ${a.alert_type === 'critical' ? 'pill-escalated' : a.alert_type === 'warning' ? 'pill-review' : 'pill-watch'}`}>
                      {a.alert_type}
                    </span>
                  </td>
                  <td style={{ fontSize: 11 }}>
                    {a.message?.slice(0, 80)}{a.message?.length > 80 ? '…' : ''}
                  </td>
                  <td>
                    <span className={`pill ${a.resolved ? 'pill-active' : 'pill-review'}`}>
                      {a.resolved ? 'Resolved' : 'Pending'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}