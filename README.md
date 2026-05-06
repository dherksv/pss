# Patient Safety Sentinel 

> **Real-Time Social Listening for Patient Experience & Safety Signals**
>
> An open-source AI-powered pharmacovigilance platform that monitors Reddit, Twitter/X, forums, and RSS feeds to detect adverse drug reactions, patient distress signals, and public health outbreaks — before traditional reporting systems catch them.

---

![Dashboard Overview](https://raw.githubusercontent.com/YOUR_USERNAME/patient-safety-sentinel/main/docs/screenshots/dashboard-overview.png)

---

## The Problem We Solve

### Traditional Pharmacovigilance is Too Slow

Every year, thousands of patients experience adverse drug reactions that go unreported for weeks or months before official systems detect them. The FDA's FAERS (Adverse Event Reporting System) relies on voluntary reporting — a process that is slow, manual, and captures only an estimated **1–10% of actual adverse events**.

Meanwhile, patients are talking. Every day, millions of people post about their medication experiences on Reddit, Twitter, patient forums, and healthcare communities. They describe symptoms, share concerns, and warn others — in real time.

**The gap:** No system efficiently listens to this signal at scale, cross-references it against official drug data, and surfaces it to the people who need to act on it.

### Real Impact of This Gap

- The **Marion Biotech / Doc-1 Max contaminated cough syrup** incident that killed dozens of children in India showed how delayed detection of a communal safety crisis can cost lives. Early social signals existed — parents posting in regional forums and parenting communities — but no system was watching.
- **Ozempic's undocumented side effects** (hair loss, gastroparesis, mental health impacts) were being widely discussed on social media months before regulatory bodies formally acknowledged them.
- **Health misinformation** about miracle cures and dangerous self-treatment spreads virally through the same channels, causing real harm.

---

## Our Solution

Patient Safety Sentinel is a **real-time social listening intelligence platform** purpose-built for healthcare safety monitoring.

It continuously ingests social media posts, runs them through a multi-stage NLP pipeline, cross-references them against FDA drug data, detects outbreak patterns, and surfaces actionable safety signals to analysts — with full explainability and audit trails.

### What Makes It Different

| Traditional Pharmacovigilance | Patient Safety Sentinel |
|---|---|
| Relies on voluntary reporting | Actively monitors public social data |
| Weeks to months lag | Real-time signal detection |
| 1–10% capture rate | Broad coverage across platforms |
| No pattern detection | Outbreak clustering across platforms |
| Black box results | Full XAI explanation per signal |
| Manual source discovery | Agentic source discovery AI |
| No novelty detection | FDA cross-reference + novelty scoring |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                                 │
│   Reddit (PRAW)  │  Twitter/X (twitterapi.io)  │  Forums  │  RSS   │
└─────────────────────────────────────────────────────────────────────┘
                              ↓ RawPost
┌─────────────────────────────────────────────────────────────────────┐
│                    LATENCY SCHEDULER (APScheduler)                   │
│         Real-time (5min)  │  Daily (midnight)  │  Weekly            │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                     INGESTION QUEUE (Python queue.Queue)             │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      PROCESSING PIPELINE (6 steps)                   │
│  1. PII/PHI Scanner      → redact before any processing             │
│  2. Relevance Filter     → discard noise early                      │
│  3. NER Extractor        → BioBERT + spaCy + RxNorm normalization   │
│  4. Signal Classifier    → ADR / Distress / Misinfo / General       │
│  5. Scorer               → Sentiment + Novelty + FDA cross-ref      │
│  6. XAI Explainer        → Human-readable explanation per signal    │
└─────────────────────────────────────────────────────────────────────┘
                              ↓ Signal Genome
┌──────────────────────────┐    ┌──────────────────────────────────────┐
│   SQLite (metadata)      │    │   ChromaDB (vector embeddings)        │
│   genomes, projects,     │    │   semantic similarity search          │
│   outbreaks, alerts      │    │   novelty scoring backbone            │
└──────────────────────────┘    └──────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                       ANALYSIS ENGINE                                │
│  Outbreak Detector  │  Trend Analyzer  │  Source Discovery Agent    │
│  (3 trigger rules)  │  (Google Trends) │  (Agentic — bonus)         │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    FastAPI + WebSocket                               │
│   REST endpoints for all data  │  /ws/feed for live genome stream   │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                     DASHBOARD (React + Vite)                         │
│  Live Feed  │  Outbreak Monitor  │  Trends  │  Config  │  Alerts   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Screenshots

### Live Signal Feed
![Live Feed](https://raw.githubusercontent.com/YOUR_USERNAME/patient-safety-sentinel/main/docs/screenshots/live-feed.png)

*Real-time genome cards streaming in as posts are processed. Each card shows source, signal type, detected entities, novelty score, and confidence.*

### Outbreak Monitor
![Outbreak Monitor](https://raw.githubusercontent.com/YOUR_USERNAME/patient-safety-sentinel/main/docs/screenshots/outbreak-monitor.png)

*Active outbreak clusters with severity badges (WATCH / WARNING / ALERT / CRITICAL), affected regions, and propagation graph.*

### Signal Genome Detail
![Genome Detail](https://raw.githubusercontent.com/YOUR_USERNAME/patient-safety-sentinel/main/docs/screenshots/genome-detail.png)

*Full genome inspection: entities extracted, FDA label cross-reference, novelty score, PII detection status, and XAI explanation.*

### Trend Analysis
![Trends](https://raw.githubusercontent.com/YOUR_USERNAME/patient-safety-sentinel/main/docs/screenshots/trends.png)

*30-day signal volume chart for a drug, top entities, and signal type breakdown.*

### Source Discovery Agent
![Source Discovery](https://raw.githubusercontent.com/YOUR_USERNAME/patient-safety-sentinel/main/docs/screenshots/source-discovery.png)

*Agentic source discovery — type a topic, the agent finds and scores relevant communities automatically.*

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Crawlers | PRAW, requests, BeautifulSoup, feedparser | Platform-native, extensible |
| Queue | Python `queue.Queue` | Simple, no infrastructure |
| Scheduler | APScheduler | 3 latency modes, lightweight |
| NER | BioBERT (`d4data/biomedical-ner-all`) | Biomedical-specific entity extraction |
| Sentiment | Twitter-RoBERTa | Trained on social media text |
| Distress | `j-hartmann/emotion-english-distilroberta-base` | Emotion classification |
| Drug norm | RxNorm NIH API | Free, canonical drug names |
| FDA cross-ref | OpenFDA API | Free, no key, label + FAERS data |
| Vector DB | ChromaDB | Local, Python-native, free |
| Metadata DB | SQLite | Zero-setup, reliable |
| Backend | FastAPI + WebSocket | Fast async Python |
| Frontend | React + Vite | Fast, lightweight SPA |
| DevOps | Docker Compose | One command to run everything |

---

## Key Features

### Signal Genome
Every social post is transformed into a structured **Signal Genome** — a rich intelligence object containing:
- Extracted entities (drugs, symptoms, conditions, locations)
- Sentiment score, distress level, confidence score
- Novelty score (cross-referenced against FDA label and FAERS database)
- PII/PHI detection and redaction status
- Natural language XAI explanation

### Novelty Scoring
```
novelty_score = label_factor + faers_factor

label_factor = 0.0 if symptom in FDA label else 0.5
faers_factor = max(0.0, 0.5 - (faers_count / 10000))
```
High novelty (>0.7) means a potentially undocumented adverse signal. This is the core scientific contribution — cross-referencing social signals against the FDA's own data in real time.

### Outbreak Pattern Detector
Three independent trigger conditions — any one fires a cluster alert:
1. **Volume spike** — same drug+symptom in >10 posts within 6 hours
2. **Novelty convergence** — 3+ high-novelty genomes for same drug+symptom pair
3. **Cross-platform convergence** — same signal appearing on 3+ distinct platforms

Severity levels: `watch → warning → alert → critical`

### Source Discovery Agent (Agentic)
Given a topic or drug name, the agent:
1. Searches for relevant online communities
2. Scores each for relevance and credibility
3. Flags low-credibility sources automatically
4. Proposes sources for human approval before monitoring begins

### PII/PHI Protection
Every post is scanned for personal information **before** any NLP processing:
- Person name detection (spaCy NER)
- Email, phone, SSN, DOB, MRN pattern matching
- Automatic redaction before storage
- Full audit trail of what was detected

---

## Project Structure

```
patient-safety-sentinel/
├── backend/
│   ├── crawlers/
│   │   ├── base.py              # Abstract crawler + RawPost schema
│   │   ├── reddit.py            # PRAW-based Reddit crawler
│   │   ├── twitter.py           # twitterapi.io crawler
│   │   ├── forum.py             # BeautifulSoup forum crawler
│   │   └── rss.py               # feedparser RSS crawler
│   ├── pipeline/
│   │   ├── processor.py         # 6-step pipeline orchestrator
│   │   ├── pii_scanner.py       # PII/PHI detection (step 1)
│   │   ├── relevance.py         # Noise filter (step 2)
│   │   ├── ner.py               # Entity extraction (step 3)
│   │   ├── classifier.py        # Signal classification (step 4)
│   │   └── scorer.py            # Scoring + FDA cross-ref (step 5)
│   ├── models/
│   │   └── genome.py            # Signal Genome + Outbreak dataclasses
│   ├── storage/
│   │   ├── sqlite_store.py      # SQLite metadata layer
│   │   └── chroma_store.py      # ChromaDB vector store
│   ├── analysis/
│   │   ├── outbreak_detector.py # 3-condition outbreak detection
│   │   └── trend_analyzer.py    # Signal trends + Google Trends
│   ├── agents/
│   │   └── source_discovery.py  # Agentic source finder
│   ├── routes/
│   │   ├── projects.py          # Project CRUD API
│   │   ├── signals.py           # Genome read API
│   │   ├── analysis.py          # Trends API
│   │   ├── sources.py           # Source discovery API
│   │   └── alerts.py            # Alerts + outbreaks API
│   ├── main.py                  # FastAPI app + WebSocket manager
│   ├── worker.py                # Background pipeline worker
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── GenomeCard.tsx   # Signal card + detail pane
│   │   │   ├── LiveFeed.tsx     # Real-time genome feed
│   │   │   ├── OutbreakPanel.tsx
│   │   │   ├── TrendPanel.tsx
│   │   │   ├── ConfigPanel.tsx  # Project setup + agent UI
│   │   │   └── AlertsPanel.tsx
│   │   ├── hooks/
│   │   │   └── useGenomeFeed.ts # WebSocket hook
│   │   ├── lib/
│   │   │   └── api.ts           # Backend API client
│   │   ├── pages/
│   │   │   └── index.tsx        # Main dashboard router
│   │   ├── main.tsx
│   │   └── portal.css
│   ├── index.html
│   ├── vite.config.ts
│   ├── package.json
│   └── Dockerfile
├── contracts/
│   ├── raw_post_schema.json     # Crawler output contract
│   └── genome_schema.json       # Signal Genome contract
├── scripts/
│   ├── seed_data.py             # Pre-seed demo data
│   ├── test_pipeline.py         # Smoke test
│   └── download_models.py       # Pre-download NLP models
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Quick Start

### Prerequisites
- Docker Desktop with WSL2 integration (Windows) or Docker Engine (Linux/Mac)
- Git
- 4GB free disk space (for NLP models)

### Step 1 — Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/patient-safety-sentinel.git
cd patient-safety-sentinel
```

### Step 2 — Set up environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your API keys:

```bash
# Reddit — register at https://www.reddit.com/prefs/apps
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_SECRET=your_reddit_secret
REDDIT_USER_AGENT=PatientSafetySentinel/1.0 by YourUsername

# Twitter — via twitterapi.io
TWITTER_API_KEY=your_twitter_api_key

# App config
SECRET_KEY=generate_any_random_string_here
DEBUG=true
CORS_ORIGINS=http://localhost:3000

# Model cache paths (do not change)
TRANSFORMERS_CACHE=/app/models_cache
HF_HOME=/app/models_cache
TRANSFORMERS_OFFLINE=1
```

### Step 3 — Download NLP Models (one-time setup)

The NLP models must be downloaded to your local machine before building Docker. They total approximately 1.5GB.

```bash
# Install dependencies for download script
pip install transformers torch

# Run the model download script
python scripts/download_models.py
```

This creates a `backend/models_cache/` folder with all three models pre-downloaded. Docker will copy this folder into the image at build time — no internet needed at runtime.

> ⚠️ The `backend/models_cache/` folder is in `.gitignore` — never commit models to GitHub.

### Step 4 — Get Reddit API credentials

1. Go to https://www.reddit.com/prefs/apps
2. Click **"create another app"**
3. Select type: **script**
4. Redirect URI: `http://localhost:8080`
5. Copy the **client ID** (below the app name) and **secret**
6. Paste into your `.env` file

### Step 5 — Build and run

```bash
docker compose up --build
```

First build takes 5–10 minutes. Subsequent builds are fast.

### Step 6 — Seed demo data

In a new terminal:

```bash
docker compose exec api python scripts/seed_data.py
```

### Step 7 — Open the dashboard

| Service | URL |
|---|---|
| 🖥️ Dashboard | http://localhost:3000 |
| 🔌 API | http://localhost:8000 |
| 📖 API Docs | http://localhost:8000/docs |

---

## Model Download Script

Save this as `scripts/download_models.py` and run it once before your first Docker build:

```python
"""
scripts/download_models.py
Downloads all NLP models to backend/models_cache/ before Docker build.
Run once: python scripts/download_models.py
"""
import os
import sys

# Set cache to project folder — Docker will COPY this in
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "backend", "models_cache")
CACHE_DIR = os.path.abspath(CACHE_DIR)

os.makedirs(CACHE_DIR, exist_ok=True)
os.environ["TRANSFORMERS_CACHE"] = CACHE_DIR
os.environ["HF_HOME"]            = CACHE_DIR

print(f"Downloading models to: {CACHE_DIR}")
print("This will take 10–20 minutes and use ~1.5GB of disk space.\n")

from transformers import pipeline

# Model 1 — Biomedical NER
print("1/3 Downloading biomedical NER model (d4data/biomedical-ner-all)...")
try:
    pipeline("token-classification",
             model="d4data/biomedical-ner-all",
             aggregation_strategy="simple")
    print("    ✓ Biomedical NER ready\n")
except Exception as e:
    print(f"    ✗ Failed: {e}\n")
    sys.exit(1)

# Model 2 — Sentiment analysis
print("2/3 Downloading sentiment model (cardiffnlp/twitter-roberta-base-sentiment-latest)...")
try:
    pipeline("sentiment-analysis",
             model="cardiffnlp/twitter-roberta-base-sentiment-latest")
    print("    ✓ Sentiment model ready\n")
except Exception as e:
    print(f"    ✗ Failed: {e}\n")
    sys.exit(1)

# Model 3 — Emotion / distress classification
print("3/3 Downloading emotion model (j-hartmann/emotion-english-distilroberta-base)...")
try:
    pipeline("text-classification",
             model="j-hartmann/emotion-english-distilroberta-base",
             return_all_scores=True)
    print("    ✓ Emotion model ready\n")
except Exception as e:
    print(f"    ✗ Failed: {e}\n")
    sys.exit(1)

print("=" * 50)
print("All models downloaded successfully.")
print(f"Location: {CACHE_DIR}")
print("\nYou can now run: docker compose up --build")
print("=" * 50)
```

---

## API Reference

All endpoints are auto-documented at `http://localhost:8000/docs`

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Service health check |
| `GET` | `/api/projects/` | List monitoring projects |
| `POST` | `/api/projects/` | Create monitoring project |
| `GET` | `/api/projects/{id}` | Get project by ID |
| `PATCH` | `/api/projects/{id}` | Update project |
| `GET` | `/api/signals/` | List signal genomes (filterable) |
| `GET` | `/api/signals/stats` | Signal counts by type |
| `GET` | `/api/signals/{id}` | Get single genome |
| `GET` | `/api/analysis/trends/{drug}` | 30-day signal trend |
| `GET` | `/api/analysis/top-entities` | Top drugs and symptoms |
| `GET` | `/api/analysis/google-trends` | Google Trends correlation |
| `POST` | `/api/sources/discover` | Trigger source discovery agent |
| `POST` | `/api/sources/approve` | Approve discovered sources |
| `GET` | `/api/alerts/` | List alerts |
| `PATCH` | `/api/alerts/{id}/resolve` | Resolve an alert |
| `GET` | `/api/alerts/outbreaks` | List outbreak records |
| `GET` | `/api/alerts/outbreaks/{id}` | Get outbreak detail |
| `WS` | `/ws/feed` | Live genome stream |

---

## Useful Commands

```bash
# Start everything
docker compose up -d

# View logs
docker compose logs -f worker     # pipeline worker
docker compose logs -f api        # FastAPI backend
docker compose logs -f frontend   # React frontend

# Smoke test the pipeline
docker compose exec api python scripts/test_pipeline.py

# Seed demo data
docker compose exec api python scripts/seed_data.py

# Open a shell in any container
docker compose exec api bash
docker compose exec worker bash
docker compose exec frontend sh

# Stop everything
docker compose down

# Full reset (wipes database)
docker compose down -v
docker compose up --build

# Check SQLite data directly
docker compose exec api bash
sqlite3 /app/db/sentinel.db "SELECT source, signal_type, created_at FROM genomes LIMIT 10;"
```

---

## Troubleshooting

**`vite: Permission denied` in frontend container**
```bash
docker compose exec frontend sh
chmod +x node_modules/.bin/vite
exit
docker compose restart frontend
```

**`en_core_web_sm` not found (spaCy)**
```bash
# Install directly via wheel URL
docker compose exec worker bash
pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl --no-deps
exit
docker compose restart worker
```

**Models trying to download at runtime**

Make sure your `.env` has:
```
TRANSFORMERS_OFFLINE=1
TRANSFORMERS_CACHE=/app/models_cache
HF_HOME=/app/models_cache
```
And confirm `backend/models_cache/` exists and has content before building.

**Worker crashes on startup**

All model loads must be lazy (inside functions, not at module level). Check that no pipeline file has a model loaded outside a function.

**Reddit API 401 errors**

Confirm your `.env` has correct `REDDIT_CLIENT_ID`, `REDDIT_SECRET`, and that `REDDIT_USER_AGENT` matches the format `AppName/1.0 by YourRedditUsername`.

---

## Contributing

This project was built for the **AI for Bharat Hackathon**. Contributions are welcome.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "feat: description"`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request to `dev`

### Branch Strategy
```
main    ← stable, demo-ready
dev     ← daily integration
feature/xxx ← individual work
```

### Contracts
The files in `contracts/` define the data schemas shared between components. **Do not change these without team agreement.**

---

## Team

| Role | Owns |
|---|---|
| Engineer A | Crawlers, Scheduler, Queue, SQLite |
| Engineer B | NLP Pipeline, ChromaDB, Analysis Engine, Agents |
| Engineer C | FastAPI, WebSocket, React Dashboard |

---

## License

MIT License — see [LICENSE](LICENSE)

---

## Acknowledgements

- [OpenFDA API](https://open.fda.gov/apis/) — free drug label and adverse event data
- [NIH RxNorm API](https://rxnav.nlm.nih.gov/) — free drug name normalization
- [HuggingFace Transformers](https://huggingface.co/) — pretrained NLP models
- [PRAW](https://praw.readthedocs.io/) — Python Reddit API Wrapper
- [twitterapi.io](https://twitterapi.io) — Twitter/X data access
- [ChromaDB](https://www.trychroma.com/) — local vector database
