import { useState, useEffect, useRef } from 'react';
import { api } from '../lib/api';

function getWsUrl() {
  // Use relative path so Vite proxy can handle it
  return '/ws/feed';
}

export function useGenomeFeed() {
  const [genomes, setGenomes]     = useState<any[]>([]);
  const [connected, setConnected] = useState(false);
  const [last, setLast]           = useState<any>(null);
  const [loading, setLoading]     = useState(true);
  const wsRef = useRef<WebSocket | null>(null);

  // Fetch historical data on mount
  useEffect(() => {
    const fetchHistorical = async () => {
      try {
        const historical = await api.getSignals({ limit: '50' });
        setGenomes(historical);
        if (historical.length > 0) {
          setLast(historical[0]);
        }
      } catch (error) {
        console.error('Failed to fetch historical signals:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchHistorical();
  }, []);

  useEffect(() => {
    let alive = true;

    function connect() {
      try {
        const ws = new WebSocket(getWsUrl());
        wsRef.current = ws;

        ws.onopen    = () => { if (alive) setConnected(true); };
        ws.onclose   = () => { if (!alive) return; setConnected(false); setTimeout(connect, 3000); };
        ws.onerror   = (error) => {
          console.error('WebSocket error:', error);
          ws.close();
        };
        ws.onmessage = (e) => {
          try {
            const g = JSON.parse(e.data);
            setLast(g);
            setGenomes(prev => [g, ...prev].slice(0, 150));
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error);
          }
        };
      } catch (error) {
        console.error('Failed to create WebSocket connection:', error);
        setTimeout(connect, 5000);
      }
    }

    connect();
    return () => { alive = false; wsRef.current?.close(); };
  }, []);

  return { genomes, connected, last, loading };
}