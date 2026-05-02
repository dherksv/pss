/**
 * pages/index.tsx - Main dashboard | OWNER: Engineer C
 * Five panels:
 *  1. LiveFeed     — real-time genome stream
 *  2. OutbreakPanel— active clusters + severity
 *  3. TrendPanel   — signal timeline charts
 *  4. ConfigPanel  — project setup + source discovery
 *  5. AlertsPanel  — critical flags + audit trail
 */
import { useState } from "react";
import LiveFeed      from "../components/LiveFeed";
import OutbreakPanel from "../components/OutbreakPanel";
import TrendPanel    from "../components/TrendPanel";
import ConfigPanel   from "../components/ConfigPanel";
import AlertsPanel   from "../components/AlertsPanel";
import { useGenomeFeed } from "../hooks/useGenomeFeed";

const TABS = ["Live Feed", "Outbreaks", "Trends", "Config", "Alerts"];

export default function Dashboard() {
  const [activeTab, setActiveTab]   = useState("Live Feed");
  const { genomes, connected, lastGenome } = useGenomeFeed();

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Patient Safety Sentinel</h1>
          <p className="text-xs text-gray-400">Real-Time Social Listening for Healthcare Signals</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${connected ? "bg-green-400" : "bg-red-400"}`}/>
          <span className="text-xs text-gray-400">{connected ? "Live" : "Disconnected"}</span>
        </div>
      </header>

      {/* Tab nav */}
      <nav className="border-b border-gray-800 px-6 flex gap-1">
        {TABS.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-3 text-sm font-medium transition-colors
              ${activeTab === tab
                ? "text-blue-400 border-b-2 border-blue-400"
                : "text-gray-400 hover:text-white"}`}
          >
            {tab}
          </button>
        ))}
      </nav>

      {/* Panel */}
      <main className="p-6">
        {activeTab === "Live Feed"  && <LiveFeed genomes={genomes} lastGenome={lastGenome}/>}
        {activeTab === "Outbreaks"  && <OutbreakPanel />}
        {activeTab === "Trends"     && <TrendPanel />}
        {activeTab === "Config"     && <ConfigPanel />}
        {activeTab === "Alerts"     && <AlertsPanel />}
      </main>
    </div>
  );
}
