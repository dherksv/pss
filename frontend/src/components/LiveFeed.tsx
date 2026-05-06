import { useState } from 'react';
import { GenomeCard, GenomeDetail } from './GenomeCard';

interface Props {
  genomes: any[];
  connected: boolean;
}

export default function LiveFeed({ genomes, connected }: Props) {
  const [selected, setSelected] = useState<any>(null);
  const [filter, setFilter]     = useState('all');

  const filtered = filter === 'all'
    ? genomes
    : genomes.filter(g => g.signal_type === filter);

  return (
    <div className="grid-2-1" style={{ alignItems:'start' }}>
      {/* Feed list */}
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
              style={{ height:26 }}>
              <option value="all">All types</option>
              <option value="adverse_drug_reaction">ADR</option>
              <option value="distress">Distress</option>
              <option value="misinformation">Misinfo</option>
              <option value="treatment_dissatisfaction">Dissatisfaction</option>
              <option value="general">General</option>
            </select>
          </div>
        </div>

        <div className="genome-feed">
          {filtered.length === 0 && (
            <div className="empty-state">
              Waiting for signals…<br/>
              <span style={{ fontSize:10 }}>Make sure worker is running</span>
            </div>
          )}
          {filtered.map(g => (
            <GenomeCard key={g.genome_id} g={g}
              selected={selected?.genome_id === g.genome_id}
              onClick={() => setSelected(g)} />
          ))}
        </div>
      </div>

      {/* Detail pane */}
      <div className="panel" style={{ position:'sticky', top:64 }}>
        {selected
          ? <GenomeDetail g={selected} />
          : (
            <div style={{ padding:40, textAlign:'center' }}>
              <div className="empty-state">
                ← Select a signal<br/>to inspect its genome
              </div>
            </div>
          )}
      </div>
    </div>
  );
}