import { useState, useEffect, useRef } from 'react';

function getWsUrl() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/ws/feed`;
}

export function useGenomeFeed() {
  const [genomes, setGenomes]     = useState<any[]>([]);
  const [connected, setConnected] = useState(false);
  const [last, setLast]           = useState<any>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let alive = true;

    function connect() {
      try {
        const ws = new WebSocket(getWsUrl());
        wsRef.current = ws;

        ws.onopen    = () => { if (alive) setConnected(true); };
        ws.onclose   = () => { if (!alive) return; setConnected(false); setTimeout(connect, 3000); };
        ws.onerror   = () => ws.close();
        ws.onmessage = (e) => {
          try {
            const g = JSON.parse(e.data);
            setLast(g);
            setGenomes(prev => [g, ...prev].slice(0, 150));
          } catch {}
        };
      } catch { setTimeout(connect, 5000); }
    }

    connect();
    return () => { alive = false; wsRef.current?.close(); };
  }, []);

  return { genomes, connected, last };
}