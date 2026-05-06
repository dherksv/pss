import { useState, useEffect } from 'react';
import { api } from '../lib/api';

function pct(n: number) { return `${(n*100).toFixed(0)}%`; }
function ago(ts: string) {
  const d = Date.now() - new Date(ts).getTime();
  if (d < 3600000) return `${Math.floor(d/60000)}m ago`;
  return `${Math.floor(d/3600000)}h ago`;
}

const DEMO = [
  { outbreak_id:'o1', trigger_drug:'Doc-1 Max', trigger_symptom:'respiratory failure',
    severity:'alert', source_count:47, platform_count:3,
    regions:['Kerala','Tamil Nadu','Karnataka'],
    summary:'47 users across Reddit, Twitter, and forums reported respiratory failure linked to Doc-1 Max in the last 6 hours. Cross-platform convergence detected.',
    confidence:0.94, created_at: new Date(Date.now()-3600000).toISOString() },
  { outbreak_id:'o2', trigger_drug:'Ozempic', trigger_symptom:'hair loss',
    severity:'warning', source_count:34, platform_count:2,
    regions:['US','IN'],
    summary:'34 users on Reddit and X reported hair loss linked to Ozempic in last 7 days. Symptom not in FDA label.',
    confidence:0.78, created_at: new Date(Date.now()-86400000).toISOString() },
];

export default function OutbreakPanel() {
  const [outbreaks, setOutbreaks] = useState<any[]>(DEMO);
  const [selected, setSelected]   = useState<any>(DEMO[0]);

  useEffect(() => {
    api.getOutbreaks()
      .then(data => { setOutbreaks(data); setSelected(data[0] || null); })
      .catch(() => {});  // keep demo data on failure
  }, []);

  return (
    <div className="grid-2-1" style={{ alignItems:'start' }}>
      {/* Outbreak list */}
      <div className="panel">
        <div className="panel-hdr">
          <div>
            <div className="panel-kicker">Pattern detector</div>
            <div className="panel-title">Active Outbreak Clusters</div>
          </div>
          <span className="p-btn" style={{ cursor:'default' }}>
            {outbreaks.length} active
          </span>
        </div>

        <div className="outbreak-list">
          {outbreaks.map(o => (
            <div key={o.outbreak_id}
              className={`outbreak-card sev-${o.severity} ${selected?.outbreak_id===o.outbreak_id?'selected':''}`}
              onClick={() => setSelected(o)}
              style={{ cursor:'pointer' }}>
              <div className="outbreak-hdr">
                <span className="outbreak-drug">{o.trigger_drug}</span>
                <span className={`pill pill-${o.severity}`}>{o.severity.toUpperCase()}</span>
              </div>
              <div className="outbreak-summary">{o.trigger_symptom}</div>
              <div className="outbreak-meta">
                <span className="outbreak-stat">📊 <strong>{o.source_count}</strong> reports</span>
                <span className="outbreak-stat">🌐 <strong>{o.platform_count}</strong> platforms</span>
                <span className="outbreak-stat">📍 <strong>{o.regions?.length}</strong> regions</span>
                <span className="outbreak-stat">⚡ <strong>{pct(o.confidence||0)}</strong> conf</span>
                <span className="outbreak-stat">🕐 {ago(o.created_at)}</span>
              </div>
            </div>
          ))}
          {outbreaks.length === 0 && <div className="empty-state">No active outbreaks</div>}
        </div>
      </div>

      {/* Detail */}
      <div className="panel" style={{ position:'sticky', top:64 }}>
        {selected ? (
          <div className="genome-detail">
            <div className="panel-hdr">
              <div>
                <div className="panel-kicker">Outbreak detail</div>
                <div className="panel-title">{selected.trigger_drug}</div>
              </div>
              <span className={`pill pill-${selected.severity}`}>
                {selected.severity.toUpperCase()}
              </span>
            </div>

            <div className="detail-section">
              <div className="detail-section-title">Trigger</div>
              <div className="detail-row"><span className="detail-key">Drug</span><span className="detail-val">{selected.trigger_drug}</span></div>
              <div className="detail-row"><span className="detail-key">Symptom</span><span className="detail-val">{selected.trigger_symptom}</span></div>
              <div className="detail-row"><span className="detail-key">Detected</span><span className="detail-val">{ago(selected.created_at)}</span></div>
              <div className="detail-row"><span className="detail-key">Confidence</span><span className="detail-val">{pct(selected.confidence||0)}</span></div>
            </div>

            <div className="detail-section">
              <div className="detail-section-title">Affected Regions</div>
              <div className="entity-chips">
                {selected.regions?.map((r: string) => (
                  <span key={r} className="entity-chip location">{r}</span>
                ))}
              </div>
            </div>

            <div className="panel-kicker" style={{ marginBottom:4 }}>Summary</div>
            <div className="explanation-box">{selected.summary}</div>

            {/* Propagation graph */}
            <div className="panel-kicker" style={{ marginTop:14, marginBottom:6 }}>
              Signal Propagation
            </div>
            <div className="graph-canvas">
              <div className="g-node accent"  style={{ top:'28%', left:'14%' }}>Reddit</div>
              <div className="g-node warning" style={{ top:'65%', left:'28%' }}>Forums</div>
              <div className="g-node danger"  style={{ top:'32%', left:'58%' }}>Twitter/X</div>
              <div className="g-node purple"  style={{ top:'65%', left:'70%' }}>⚠ OUTBREAK</div>
              <div className="g-edge" style={{ top:'33%', left:'22%', width:'36%', transform:'rotate(4deg)' }}/>
              <div className="g-edge" style={{ top:'57%', left:'36%', width:'28%', transform:'rotate(-20deg)' }}/>
            </div>
          </div>
        ) : <div className="empty-state">Select an outbreak</div>}
      </div>
    </div>
  );
}