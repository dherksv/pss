# Engineer C — Frontend Dashboard + Backend API Layer

## Your Role
You own the presentation layer and the API. Your job is to make everything
the other two engineers built visible, beautiful, and usable. The dashboard
is the product judges will see. The API is what connects the frontend to
the backend intelligence.

## What We Are Building
Patient Safety Sentinel — a real-time social listening system for healthcare.
The dashboard has five panels: Live Feed (genomes streaming in real time),
Outbreak Monitor (safety clusters with severity badges), Trend Analysis
(Ozempic 30-day signal chart), Project Config (setup + Source Discovery Agent),
and Alerts (critical flags + audit trail).

## System Architecture (Your Layers)
```
[Pipeline + Analysis — Engineer B builds this]
        ↓
[FastAPI + WebSocket — YOU build this]
  backend/main.py           — app setup, WebSocket manager
  backend/routes/projects.py — CRUD for monitoring projects
  backend/routes/signals.py  — genome read API
  backend/routes/analysis.py — trends + Google Trends
  backend/routes/sources.py  — source discovery agent trigger
  backend/routes/alerts.py   — alerts + outbreaks
        ↓
[Next.js Dashboard — YOU build this]
  LiveFeed      — WebSocket genome cards, real time
  OutbreakPanel — active clusters, severity badges, timeline
  TrendPanel    — recharts line charts for signal volume
  ConfigPanel   — project setup form, source discovery UI
  AlertsPanel   — alert list, resolve button, audit trail
  GenomeCard    — reusable card showing one genome detail
```

## Your Files to Implement
```
backend/main.py                    ✅ scaffold — wire WebSocket broadcast
backend/routes/projects.py         ✅ scaffold — test all endpoints
backend/routes/signals.py          ✅ scaffold — add pagination
backend/routes/analysis.py         ✅ scaffold — test trend endpoints
backend/routes/sources.py          ✅ scaffold — test discovery agent
backend/routes/alerts.py           ✅ scaffold — test resolve flow

frontend/src/pages/index.tsx       ✅ scaffold — implement tab switching
frontend/src/hooks/useGenomeFeed.ts✅ scaffold — test WebSocket connection
frontend/src/lib/api.ts            ✅ scaffold — add error handling
frontend/src/components/LiveFeed.tsx       🔧 implement genome card stream
frontend/src/components/OutbreakPanel.tsx  🔧 implement cluster view
frontend/src/components/TrendPanel.tsx     🔧 implement recharts timeline
frontend/src/components/ConfigPanel.tsx    🔧 implement project form + agent UI
frontend/src/components/AlertsPanel.tsx    🔧 implement alert list
frontend/src/components/GenomeCard.tsx     🔧 implement genome detail card
```

## Critical WebSocket Integration
The backend pushes genomes via WebSocket. You need to broadcast from
the pipeline worker to connected dashboard clients. Wire this in main.py:

```python
# In worker.py after genome is stored, call:
import httpx
httpx.post("http://localhost:8000/internal/broadcast", json=genome.to_dict())

# In main.py add internal route:
@app.post("/internal/broadcast")
async def internal_broadcast(genome: dict):
    await manager.broadcast(genome)
```

## Key UI Priorities (in order)
1. LiveFeed — genome cards appearing in real time. Each card shows:
   source badge, signal_type badge, drug name, symptom, sentiment bar,
   novelty score, confidence score, explanation text. Click to expand full genome.

2. OutbreakPanel — severity badge (WATCH/WARNING/ALERT/CRITICAL) in red/amber/red.
   Timeline showing how cluster grew. Summary text. Platform list.

3. TrendPanel — recharts LineChart showing daily signal count for Ozempic
   over 30 days. Second chart showing sentiment trend. Simple and clear.

4. ConfigPanel — form to create a project (name, keywords, sources).
   Source Discovery Agent section: user types a topic, clicks Discover,
   sees ranked list of communities with relevance + credibility scores,
   checkboxes to approve/reject each.

5. AlertsPanel — list of unresolved alerts, Resolve button, audit trail.

## API Endpoints You Serve
```
GET  /api/projects/             → list all projects
POST /api/projects/             → create project
GET  /api/signals/?drug=Ozempic → filter genomes
GET  /api/analysis/trends/Ozempic?days=30
GET  /api/analysis/google-trends?keywords=Ozempic+side+effects
POST /api/sources/discover      → trigger agent
GET  /api/alerts/outbreaks      → active outbreak records
WS   /ws/feed                   → live genome stream
```
All endpoints are documented at http://localhost:8000/docs (auto-generated).

## How to Test
```bash
# Start the stack
docker compose up --build

# Test API
curl http://localhost:8000/health
curl http://localhost:8000/api/signals/?limit=5

# Check API docs
open http://localhost:8000/docs

# Check frontend
open http://localhost:3000
```

## How to Collaborate
- Work on branch: feature/dashboard-livefeed, feature/dashboard-outbreak
- Merge to dev every evening
- If you need a new API field from Engineer B → ask before changing genome.py
- If you need a new endpoint → add it to routes/, tell both engineers
- Your daily standup: "API returning data? WebSocket pushing? UI rendering?"

## Demo Flow You Must Support (Rehearse This)
1. Show project config — create Ozempic project live
2. Source Discovery Agent — type "Ozempic side effects", show ranked sources
3. Switch to Live Feed — genomes appearing (pre-seeded + live Reddit)
4. Click a genome — show full genome detail with explanation
5. Switch to Outbreaks — show contaminated syrup cluster, severity=ALERT
6. Switch to Trends — show Ozempic hair loss signal rising over 30 days
Total demo time: 4-5 minutes. Practice it.
