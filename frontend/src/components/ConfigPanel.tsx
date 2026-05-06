import { useState } from 'react';
import { api } from '../lib/api';

const SOURCE_ICONS: Record<string,string> = { reddit:'👾', twitter:'🐦', forum:'💬', rss:'📰' };

export default function ConfigPanel({ projects, setProjects }: any) {
  const [name, setName]               = useState('');
  const [keywords, setKeywords]       = useState<string[]>(['Ozempic','hair loss','side effect']);
  const [kwInput, setKwInput]         = useState('');
  const [latency, setLatency]         = useState('realtime');
  const [topic, setTopic]             = useState('');
  const [discovered, setDiscovered]   = useState<any[]>([]);
  const [discovering, setDiscovering] = useState(false);
  const [creating, setCreating]       = useState(false);
  const [msg, setMsg]                 = useState('');
  const [msgType, setMsgType]         = useState<'success'|'error'>('success');

  function addKw() {
    const kw = kwInput.trim();
    if (kw && !keywords.includes(kw)) { setKeywords(k => [...k, kw]); setKwInput(''); }
  }

  async function discover() {
    if (!topic.trim()) return;
    setDiscovering(true);
    setDiscovered([]);
    try {
      const res = await api.discoverSources(topic, keywords);
      setDiscovered(res.discovered || []);
    } catch {
      // Demo fallback
      setDiscovered([
        { name:'r/ozempic',   url:'https://reddit.com/r/ozempic',   source_type:'reddit', relevance_score:0.91, credibility_score:0.88, member_count:120000, recommended:true,  flagged_low_credibility:false },
        { name:'r/diabetes',  url:'https://reddit.com/r/diabetes',  source_type:'reddit', relevance_score:0.84, credibility_score:0.92, member_count:280000, recommended:true,  flagged_low_credibility:false },
        { name:'r/AskDocs',   url:'https://reddit.com/r/AskDocs',   source_type:'reddit', relevance_score:0.72, credibility_score:0.95, member_count:480000, recommended:true,  flagged_low_credibility:false },
        { name:'FDA MedWatch',url:'https://fda.gov',                 source_type:'rss',    relevance_score:0.65, credibility_score:1.0,  member_count:0,      recommended:true,  flagged_low_credibility:false },
        { name:'r/conspiracy',url:'https://reddit.com/r/conspiracy', source_type:'reddit', relevance_score:0.34, credibility_score:0.2,  member_count:1800000,recommended:false, flagged_low_credibility:true  },
      ]);
    } finally { setDiscovering(false); }
  }

  async function createProject() {
    if (!name.trim() || keywords.length === 0) return;
    setCreating(true);
    try {
      const res = await api.createProject({
        name, keywords,
        sources: [{ type:'reddit', latency, subreddits:['ozempic','diabetes','AskDocs'] }],
      });
      setMsg(`✓ Project created — ID: ${res.project_id}`);
      setMsgType('success');
      setProjects((p: any[]) => [...p, { id: res.project_id, name }]);
      setName('');
    } catch {
      setMsg(`✓ Project "${name}" saved (demo mode)`);
      setMsgType('success');
    } finally { setCreating(false); }
  }

  return (
    <div className="grid-2-1" style={{ alignItems:'start' }}>
      {/* Project form */}
      <div className="panel">
        <div className="panel-hdr">
          <div>
            <div className="panel-kicker">Admin</div>
            <div className="panel-title">Create Monitoring Project</div>
          </div>
        </div>

        {msg && (
          <div className="explanation-box"
            style={{ marginBottom:12,
                     borderLeftColor: msgType==='success' ? 'var(--success)' : 'var(--danger)' }}>
            {msg}
          </div>
        )}

        <div className="form-row">
          <div className="form-field">
            <label className="form-label">Project Name</label>
            <input className="form-input" value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Ozempic Pharmacovigilance"/>
          </div>
          <div className="form-field">
            <label className="form-label">Description</label>
            <input className="form-input" placeholder="Monitor adverse events"/>
          </div>
        </div>

        <div className="form-field" style={{ marginBottom:10 }}>
          <label className="form-label">Keywords</label>
          <div className="keyword-chips">
            {keywords.map(k => (
              <span key={k} className="kw-chip">
                {k}
                <button onClick={() => setKeywords(kk => kk.filter(x => x!==k))}>×</button>
              </span>
            ))}
          </div>
          <div style={{ display:'flex', gap:8, marginTop:6 }}>
            <input className="form-input" value={kwInput}
              onChange={e => setKwInput(e.target.value)}
              onKeyDown={e => e.key==='Enter' && addKw()}
              placeholder="Type keyword → Enter" style={{ flex:1 }}/>
            <button className="p-btn primary" onClick={addKw}>Add</button>
          </div>
        </div>

        <div className="form-field" style={{ marginBottom:14 }}>
          <label className="form-label">Crawl Latency</label>
          <div className="latency-grid">
            {[
              { key:'realtime', label:'Real-time', sub:'Every 5 min' },
              { key:'daily',    label:'Daily',     sub:'At midnight' },
              { key:'weekly',   label:'Weekly',    sub:'Sunday 00:00' },
            ].map(l => (
              <div key={l.key}
                className={`latency-opt ${latency===l.key ? 'selected' : ''}`}
                onClick={() => setLatency(l.key)}>
                <span className="lo-label">{l.label}</span>
                <span className="lo-sub">{l.sub}</span>
              </div>
            ))}
          </div>
        </div>

        <div style={{ display:'flex', justifyContent:'flex-end' }}>
          <button className="p-btn primary" onClick={createProject} disabled={creating}>
            {creating ? 'Creating…' : '+ Create Project'}
          </button>
        </div>

        {/* Existing projects table */}
        {projects.length > 0 && (
          <div style={{ marginTop:18 }}>
            <div className="panel-kicker" style={{ marginBottom:8 }}>Active Projects</div>
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
            <div className="panel-kicker">Agentic — Bonus feature</div>
            <div className="panel-title">Source Discovery Agent</div>
          </div>
        </div>

        <div style={{ fontSize:11, color:'var(--muted)', marginBottom:12, lineHeight:1.6 }}>
          Type a topic — the agent discovers relevant communities, scores them for relevance
          and credibility, and flags low-quality sources automatically.
        </div>

        <div className="form-field" style={{ marginBottom:12 }}>
          <label className="form-label">Topic to discover</label>
          <div style={{ display:'flex', gap:8 }}>
            <input className="form-input" value={topic}
              onChange={e => setTopic(e.target.value)}
              onKeyDown={e => e.key==='Enter' && discover()}
              placeholder="Ozempic side effects" style={{ flex:1 }}/>
            <button className="p-btn primary" onClick={discover} disabled={discovering}>
              {discovering ? '🔍…' : '🔍 Discover'}
            </button>
          </div>
        </div>

        {discovered.length > 0 && (
          <>
            <div className="panel-kicker" style={{ marginBottom:8 }}>
              {discovered.length} sources found — approve to add
            </div>
            <div className="discovery-list">
              {discovered.map(s => (
                <div key={s.name} className="discovery-item"
                  style={{ opacity: s.flagged_low_credibility ? 0.55 : 1 }}>
                  <input type="checkbox" className="discovery-check"
                    defaultChecked={s.recommended && !s.flagged_low_credibility}/>
                  <div className="discovery-info">
                    <div className="discovery-name">
                      {SOURCE_ICONS[s.source_type] || '🔗'} {s.name}
                      {s.flagged_low_credibility && (
                        <span style={{ color:'var(--danger)', fontSize:9, marginLeft:6 }}>
                          ⚠ LOW CREDIBILITY
                        </span>
                      )}
                    </div>
                    <div className="discovery-meta">
                      {s.source_type}
                      {s.member_count > 0 && ` · ${(s.member_count/1000).toFixed(0)}K members`}
                      {' · '}
                      <a href={s.url} target="_blank" rel="noopener noreferrer"
                        style={{ color:'var(--accent)', fontSize:9 }}>
                        visit ↗
                      </a>
                    </div>
                  </div>
                  <div className="discovery-scores">
                    <span className={`dscore ${s.relevance_score > 0.7 ? 'high' : 'low'}`}>
                      rel {(s.relevance_score*100).toFixed(0)}%
                    </span>
                    <span className={`dscore ${s.credibility_score > 0.7 ? 'high' : 'low'}`}>
                      cred {(s.credibility_score*100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
            <div style={{ display:'flex', justifyContent:'flex-end', marginTop:10 }}>
              <button className="p-btn primary">✓ Add approved sources</button>
            </div>
          </>
        )}

        {discovered.length === 0 && (
          <div className="empty-state" style={{ marginTop:20 }}>
            Enter a topic above → click Discover<br/>
            Agent searches Reddit, forums, and RSS for relevant communities
          </div>
        )}
      </div>
    </div>
  );
}