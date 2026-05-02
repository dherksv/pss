# Engineer A — Crawlers, Storage & Worker

## Your Role
You own the data ingestion layer. Your job is to get live data flowing
from sources into the processing queue reliably and on schedule.

## What We Are Building
Patient Safety Sentinel — a real-time social listening system that monitors
Reddit, Twitter/X, forums, and RSS feeds for healthcare safety signals.
Users configure "projects" with keywords (eg: "Ozempic", "hair loss") and
sources. Your crawlers collect posts matching those keywords and feed them
into a pipeline that converts them into "Signal Genomes" — structured
intelligence objects. These genomes appear live on a dashboard.

## System Architecture (Your Layers)
```
[Reddit/Twitter/Forum/RSS]
        ↓  (you build this)
[APScheduler — 3 latency modes: realtime/daily/weekly]
        ↓  (you build this)
[Python queue.Queue — decouples crawlers from pipeline]
        ↓  (you build this)
[Pipeline — Engineer B builds this, you feed into it]
        ↓
[SQLite + ChromaDB storage — you build SQLite side]
        ↓
[FastAPI + Dashboard — Engineer C builds this]
```

## Your Files to Implement
```
backend/crawlers/base.py       ✅ scaffold done — do not change RawPost schema
backend/crawlers/reddit.py     🔧 implement crawl() method
backend/crawlers/twitter.py    🔧 implement crawl() method
backend/crawlers/forum.py      🔧 implement crawl() method
backend/crawlers/rss.py        🔧 implement crawl() method
backend/worker.py              🔧 implement setup_scheduler() fully
backend/storage/sqlite_store.py✅ scaffold done — add queries if needed
```

## The Contract You Must Keep
Every crawler puts a RawPost dict on the queue. The schema is fixed in
`contracts/raw_post_schema.json` and `crawlers/base.py::make_raw_post()`.
Engineer B reads this in his pipeline. NEVER change field names.

## Priority Order (Day 1-2)
1. Get Reddit crawler working first — PRAW is well documented
2. Wire worker.py scheduler to call Reddit crawler every 5 min
3. Confirm posts appear in the queue and SQLite
4. Then Twitter crawler (limited credits — be careful)
5. Then Forum + RSS crawlers

## Reddit Setup
```python
# Register app at: https://www.reddit.com/prefs/apps
# Set in .env:
REDDIT_CLIENT_ID=your_id
REDDIT_SECRET=your_secret
REDDIT_USER_AGENT=PatientSafetySentinel/1.0 by YourUsername
```

## Twitter Setup
```python
# Use hackathon-provided twitterapi.io key
# Set in .env:
TWITTER_API_KEY=your_key
# Endpoint: https://api.twitterapi.io/twitter/tweet/advanced_search
# BE CONSERVATIVE — limited credits. Max 20 results per call.
```

## How to Test Your Work
```bash
# Start the stack
docker compose up --build

# Check logs
docker compose logs worker -f

# Run smoke test
python scripts/test_pipeline.py

# Check SQLite has data
sqlite3 db/sentinel.db "SELECT * FROM genomes LIMIT 5;"
```

## How to Collaborate
- Work on branch: feature/crawler-reddit, feature/crawler-twitter etc
- Merge to dev every evening
- If you change anything in RawPost schema → TELL BOTH ENGINEERS FIRST
- Your daily standup answer: "Crawlers running? Queue filling? SQLite has rows?"

## Demo Scenarios to Support
1. Ozempic monitoring — subreddits: r/ozempic, r/diabetes, r/loseit
2. Contaminated cough syrup — subreddits: r/Parenting, r/medicine, r/india

Seed keywords already configured in scripts/seed_data.py.
Run `python scripts/seed_data.py` to pre-populate the DB for the demo.
