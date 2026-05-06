import { useState, useEffect } from 'react';
import { useGenomeFeed } from '../hooks/useGenomeFeed';
import { api } from '../lib/api';
import LiveFeed      from '../components/LiveFeed';
import OutbreakPanel from '../components/OutbreakPanel';
import TrendPanel    from '../components/TrendPanel';
import ConfigPanel   from '../components/ConfigPanel';
import AlertsPanel   from '../components/AlertsPanel';

type View = 'live' | 'outbreaks' | 'trends' | 'config' | 'alerts';

const RAIL: { key: View; icon: string; tip: string }[] = [
  { key:'live',      icon:'◈', tip:'Live Feed'     },
  { key:'outbreaks', icon:'⚠', tip:'Outbreaks'     },
  { key:'trends',    icon:'⟋', tip:'Trends'        },
  { key:'config',    icon:'⊞', tip:'Config'        },
  { key:'alerts',    icon:'◉', tip:'Alerts'        },
];

export default function Dashboard() {
  const [view, setView]         = useState<View>('live');
  const [projects, setProjects] = useState<any[]>([]);
  const [theme, setTheme]       = useState<'dark'|'light'>('dark');

  const { genomes, connected } = useGenomeFeed();

  useEffect(() => {
    api.getProjects().then(setProjects).catch(() => {});
  }, []);

  const titles: Record<View, string> = {
    live:'Live Signal Feed', outbreaks:'Outbreak Monitor',
    trends:'Trend Analysis', config:'Project Config', alerts:'Alerts & Audit',
  };

  return (
    <div className="shell" data-theme={theme}>
      {/* Rail */}
      <aside className="rail">
        <div className="rail-logo">PSS</div>
        <nav className="rail-nav">
          {RAIL.map(r => (
            <button key={r.key}
              className={`rail-btn ${view===r.key ? 'active' : ''}`}
              onClick={() => setView(r.key)}>
              {r.icon}
              <span className="rail-tip">{r.tip}</span>
            </button>
          ))}
        </nav>
        <div className="rail-divider"/>
        <button className="rail-btn"
          title="Toggle theme"
          onClick={() => setTheme(t => t==='dark'?'light':'dark')}>
          ☀
        </button>
      </aside>

      {/* Workspace */}
      <div className="workspace">
        {/* Topbar */}
        <header className="topbar">
          <div className="topbar-left">
            <span className="breadcrumb">Sentinel / {titles[view]}</span>
            <span className="page-title">{titles[view]}</span>
          </div>
          <div className="topbar-right">
            <div className="conn-badge">
              <div className="live-dot"
                style={{ background: connected ? 'var(--success)' : 'var(--faint)' }}/>
              <span className="live-label">{connected ? 'LIVE' : 'DEMO'}</span>
            </div>
            <span className="tb-btn" style={{ cursor:'default' }}>
              {genomes.length} signals
            </span>
            <select className="tb-select" value={theme}
              onChange={e => setTheme(e.target.value as any)}>
              <option value="dark">Dark</option>
              <option value="light">Light</option>
            </select>
          </div>
        </header>

        {/* Panels */}
        <div className="content">
          {view === 'live'      && <LiveFeed genomes={genomes} connected={connected}/>}
          {view === 'outbreaks' && <OutbreakPanel/>}
          {view === 'trends'    && <TrendPanel genomes={genomes}/>}
          {view === 'config'    && <ConfigPanel projects={projects} setProjects={setProjects}/>}
          {view === 'alerts'    && <AlertsPanel/>}
        </div>
      </div>
    </div>
  );
}