/**
 * useGenomeFeed.ts - WebSocket hook for live genome stream
 * OWNER: Engineer C
 * Connects to ws://localhost:8000/ws/feed
 * Returns latest genomes array, updated in real time
 */
import { useState, useEffect, useCallback } from "react";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws/feed";
const MAX_GENOMES = 100;

export function useGenomeFeed() {
  const [genomes, setGenomes]       = useState<any[]>([]);
  const [connected, setConnected]   = useState(false);
  const [lastGenome, setLastGenome] = useState<any>(null);

  useEffect(() => {
    const ws = new WebSocket(WS_URL);

    ws.onopen  = () => setConnected(true);
    ws.onclose = () => setConnected(false);

    ws.onmessage = (event) => {
      try {
        const genome = JSON.parse(event.data);
        setLastGenome(genome);
        setGenomes(prev => [genome, ...prev].slice(0, MAX_GENOMES));
      } catch (e) {
        console.error("WebSocket parse error", e);
      }
    };

    return () => ws.close();
  }, []);

  return { genomes, connected, lastGenome };
}
