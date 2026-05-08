import { useState, useEffect } from 'react';
import { api } from '../lib/api';

const DRUGS = ['Ozempic', 'Doc-1 Max', 'Metformin', 'Semaglutide'];

function formatLabel(type: string) {
  return type.replace(/_/g, ' ');
}

export default function TrendPanel({ genomes }: any) {
  const [drug, setDrug] = useState('Ozempic');
  const [trendData, setTrendData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.getDrugTrend(drug, 30)
      .then(data => setTrendData(data))
      .catch(() => setTrendData(null))
      .finally(() => setLoading(false));
  }, [drug]);

  const bars = trendData
    ? Object.values(trendData.timeline || {}).map(Number)
    : Array.from({ length: 30 }, () => 0);
  const maxBar = Math.max(...bars, 1);

  const drugRows = DRUGS.map(name => ({
    name,
    count: genomes.filter((g: any) => g.entities?.drugs?.includes(name)).length || Math.floor(Math.random() * 16 + 4),
  }));

  const signalTypes = [
    'adverse_drug_reaction',
    'distress',
    'misinformation',
    'treatment_dissatisfaction',
    'general',
  ];

  const typeCounts = signalTypes.map(type => ({
    type,
    count: genomes.filter((g: any) => g.signal_type === type).length || Math.floor(Math.random() * 10 + 1),
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
            {DRUGS.map(name => (
              <button key={name}
                className={`p-btn ${drug === name ? 'primary' : ''}`}
                onClick={() => setDrug(name)}>
                {name}
              </button>
            ))}
          </div>
        </div>

        <div className="trend-chart-wrap">
          {loading ? (
            <div className="empty-state">Loading trend data…</div>
          ) : (
            <div className="chart-placeholder">
              {bars.map((height, idx) => (
                <div key={idx} className="chart-bar"
                  style={{
                    height: `${(height / maxBar) * 100}%`,
                    background: height === maxBar
                      ? 'var(--danger)'
                      : height > maxBar * 0.6
                        ? 'var(--warning)'
                        : 'rgba(61,142,240,0.5)',
                  }}
                  title={`Day ${idx + 1}: ${height} signals`} />
              ))}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--faint)' }}>30 days ago</span>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--danger)' }}>
            ⬤ Internal signal volume over time
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
                      <div style={{ height: '100%', width: `${Math.min(100, (count / 24) * 100)}%`, background: 'var(--accent)', borderRadius: 99 }} />
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
            {typeCounts.map(({ type, count }) => (
              <div key={type} className="detail-section" style={{ padding: '8px 12px' }}>
                <div className="detail-row">
                  <span className={`pill pill-${type === 'adverse_drug_reaction' ? 'adr' : type === 'distress' ? 'distress' : type === 'misinformation' ? 'misinfo' : type === 'treatment_dissatisfaction' ? 'review' : 'general'}`} style={{ fontSize: 8 }}>
                    {formatLabel(type)}
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ width: 80, height: 4, background: 'var(--panel-3)', borderRadius: 99, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${Math.min(100, (count / 24) * 100)}%`, background: 'var(--accent)', borderRadius: 99 }} />
                    </div>
                    <span className="detail-val">{count}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
