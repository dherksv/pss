# Patient Safety Sentinel 🏥

> Real-Time Social Listening for Patient Experience & Safety Signals

## Quick Start

```bash
git clone https://github.com/yourteam/patient-safety-sentinel
cd patient-safety-sentinel
cp .env.example .env
# Fill in your API keys in .env
docker compose up --build
```

| Service | URL |
|---|---|
| Dashboard | http://localhost:3000 |
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |

## Seed Demo Data

```bash
docker compose exec api python /app/scripts/seed_data.py
```

## Smoke Test

```bash
docker compose exec api python /app/scripts/test_pipeline.py
```

## Team Ownership

| Engineer | Branch prefix | Owns |
|---|---|---|
| Engineer A | `feature/crawler-*` | Crawlers, Scheduler, Worker, SQLite |
| Engineer B | `feature/nlp-*`, `feature/outbreak-*` | Pipeline, Models, Analysis, Agents |
| Engineer C | `feature/dashboard-*` | Frontend, FastAPI routes, WebSocket |

## Branch Strategy

```
main   ← demo-ready always, never push directly
 └── dev  ← merge here every evening, all 3 engineers
       ├── feature/crawler-reddit
       ├── feature/nlp-pipeline
       └── feature/dashboard-livefeed
```

## Contracts

Shared schemas that all engineers must agree before changing:
- `contracts/raw_post_schema.json` — output of all crawlers
- `contracts/genome_schema.json`   — Signal Genome atomic unit

## Architecture

```
[Reddit PRAW / twitterapi.io / BeautifulSoup / feedparser]
                    ↓ RawPost
           [APScheduler — realtime/daily/weekly]
                    ↓
            [Python queue.Queue]
                    ↓
         ┌──────────────────────┐
         │   Processing Pipeline│
         │  1. PII/PHI Scan     │
         │  2. Relevance Filter │
         │  3. BioBERT NER      │  + RxNorm + spaCy
         │  4. Signal Classify  │  + Mental-RoBERTa
         │  5. Score            │  + FDA APIs (free)
         │  6. XAI Explain      │
         └──────────────────────┘
                    ↓ SignalGenome
        [SQLite metadata] [ChromaDB vectors]
                    ↓
    [OutbreakDetector] [TrendAnalyzer] [SourceDiscoveryAgent]
                    ↓
           [FastAPI + WebSocket]
                    ↓
         [Next.js Dashboard]
    LiveFeed | Outbreaks | Trends | Config | Alerts
```

## Tech Stack

| Layer | Technology |
|---|---|
| Crawlers | PRAW, requests, BeautifulSoup, feedparser |
| Queue | Python queue.Queue |
| Scheduler | APScheduler |
| NLP Models | HuggingFace (BioBERT, Mental-RoBERTa, Twitter-RoBERTa) |
| Vector DB | ChromaDB (local) |
| Metadata DB | SQLite |
| External APIs | OpenFDA, RxNorm NIH, Google Trends (all free) |
| Backend | FastAPI + WebSocket |
| Frontend | Next.js + Recharts + Tailwind |
| DevOps | Docker Compose |

## Demo Scenarios

1. **Ozempic Side Effects** — pharmacovigilance, FDA novelty score, 30-day trend
2. **Contaminated Cough Syrup** — outbreak detection, cross-platform convergence, ALERT severity

## Deployment to DigitalOcean

```bash
ssh root@your_droplet_ip
git clone https://github.com/yourteam/patient-safety-sentinel
cd patient-safety-sentinel
cp .env.example .env && nano .env
docker compose up -d
```
