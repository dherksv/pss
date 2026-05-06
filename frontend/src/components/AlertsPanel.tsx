import { useState, useEffect } from 'react';
import { api } from '../lib/api';

function ago(ts: string) {
  const d = Date.now() - new Date(ts).getTime();
  if (d < 60000)   return `${Math.floor(d/1000)}s ago`;
  if (d < 3600000) return `${Math.floor(d/60000)}m ago`;
  return `${Math.floor(d/3600000)}h ago`;
}

const DEMO_ALERTS = [
  { id:1, alert_type:'critical', message:'OUTBREAK ALERT: Doc-1 Max respiratory failure — 47 reports, 3 platforms, severity: ALERT', resolved:0, created_at: new Date(Date.now()-3600000).toISOString() },
  { id:2, alert_type:'warning',  message:'High novelty: Ozempic + hair loss — not in FDA label, novelty 0.84', resolved:0, created_at: new Date(Date.now()-7200000).toISOString() },
  { id:3, alert_type:'info',     message:'Distress signal flagged for human review — Twitter post', resolved:0, created_at: new Date(Date.now()-600000).toISOString() },
];

const ICONS: Record<string,string> = { critical:'🔴', warning:'🟡', info:'🔵' };

export default function AlertsPanel() {
  const [alerts, setAlerts] = useState<any[]>(DEMO_ALERTS);

  useEffect(() => {
    api.getAlerts(false)
      .then(setAlerts)
      .catch(() => {});
  }, []);

  async function resolve(id: number) {
    await api.resolveAlert(id).catch(() => {});
    setAlerts(a => a.filter(x => x.id !== id));
  }

  const critical  = alerts.filter(a => a.alert_type==='critical').length;
  const warnings  = alerts.filter(a => a.alert_type==='warning').length;
  const info      = alerts.filter(a => a.alert_type==='info').length;

  return (
    <div className="grid-1">
      {/* Metric cards */}
      <div className="metrics-row" style={{ gridTemplateColumns:'repeat(3,1fr)' }}>
        <div className="metric-card c-danger">
          <div className="metric-label">Critical</div>
          <div className="metric-val">{critical}</div>
          <div className="metric-sub">Immediate action needed</div>
        </div>
        <div className="metric-card c-warning">
          <div className="metric-label">Warnings</div>
          <div className="metric-val">{warnings}</div>
          <div className="metric-sub">Review within 24h</div>
        </div>
        <div className="metric-card c-accent">
          <div className="metric-label">Info</div>
          <div className="metric-val">{info}</div>
          <div className="metric-sub">Informational flags</div>
        </div>
      </div>

      {/* Active alerts */}
      <div className="panel">
        <div className="panel-hdr">
          <div>
            <div className="panel-kicker">Active</div>
            <div className="panel-title">Unresolved Alerts</div>
          </div>
          <span className="p-btn" style={{ cursor:'default' }}>{alerts.length} pending</span>
        </div>
        <div className="alert-list">
          {alerts.map(a => (
            <div key={a.id} className={`alert-item ${a.alert_type}`}>
              <span className="alert-icon">{ICONS[a.alert_type] || '⚪'}</span>
              <div className="alert-body">
                <div className="alert-msg">{a.message}</div>
                <div className="alert-time">{ago(a.created_at)}</div>
              </div>
              <button className="resolve-btn" onClick={() => resolve(a.id)}>
                Resolve
              </button>
            </div>
          ))}
          {alerts.length === 0 && <div className="empty-state">All alerts resolved ✓</div>}
        </div>
      </div>

      {/* Audit trail */}
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
                <th>Time</th><th>Type</th><th>Message</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map(a => (
                <tr key={a.id}>
                  <td style={{ fontFamily:'var(--mono)', fontSize:10 }}>{ago(a.created_at)}</td>
                  <td>
                    <span className={`pill ${
                      a.alert_type==='critical' ? 'pill-escalated'
                      : a.alert_type==='warning' ? 'pill-review'
                      : 'pill-watch'
                    }`}>{a.alert_type}</span>
                  </td>
                  <td style={{ fontSize:11 }}>{a.message?.slice(0,80)}{a.message?.length>80?'…':''}</td>
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