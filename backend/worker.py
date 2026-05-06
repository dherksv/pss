"""
backend/worker.py

Patient Safety Sentinel — background worker process.
Engineer A owns this file.

Responsibilities:
    1. Call init_db() on startup
    2. Load all active projects from SQLite
    3. Register APScheduler jobs (realtime / daily / weekly) per source per project
    4. Run a pipeline_worker thread that reads RawPosts from the shared queue,
       calls Engineer B's process_post(), saves genomes to SQLite + ChromaDB,
       and pushes results to Engineer C's FastAPI WebSocket endpoint
    5. Run forever until Ctrl+C / SIGTERM

Flow:
    APScheduler → crawler.crawl() → queue.Queue → pipeline_worker thread
                                                        ↓
                                               Engineer B: process_post()
                                                        ↓
                                          save_genome() + chroma + websocket push
"""

import json
import logging
import os
import queue
import signal
import sys
import threading
import time
from datetime import datetime, timezone
import httpx

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor

from crawlers.reddit import RedditCrawler
from crawlers.twitter import TwitterCrawler
from crawlers.rss import RSSCrawler
from crawlers.forum import ForumCrawler
from storage.sqlite_store import init_db, get_active_projects, save_genome

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("worker")

# ---------------------------------------------------------------------------
# Shared queue — crawlers produce, pipeline_worker consumes
# ---------------------------------------------------------------------------
POST_QUEUE: queue.Queue = queue.Queue(maxsize=1000)

# ---------------------------------------------------------------------------
# Shutdown event — set by SIGINT/SIGTERM to stop all threads cleanly
# ---------------------------------------------------------------------------
SHUTDOWN = threading.Event()

# ---------------------------------------------------------------------------
# FastAPI WebSocket push endpoint (Engineer C)
# Internal Docker network URL — worker → api service
# ---------------------------------------------------------------------------
WS_PUSH_URL = os.getenv("WS_PUSH_URL", "http://api:8000/internal/genome")

# ---------------------------------------------------------------------------
# Crawler registry — source_type → class
# ---------------------------------------------------------------------------
CRAWLER_CLASSES = {
    "reddit":  RedditCrawler,
    "twitter": TwitterCrawler,
    "rss":     RSSCrawler,
    "forum":   ForumCrawler,
}


# ---------------------------------------------------------------------------
# Lazy import for Engineer B's pipeline
# Must be lazy — model loads happen inside process_post, never at import time
# ---------------------------------------------------------------------------
def _get_pipeline():
    """
    Import Engineer B's pipeline lazily so models load only when the
    pipeline_worker thread first needs them, not at worker.py module load.
    Raises ImportError clearly if Engineer B's module is missing.
    """
    try:
        from pipeline.processor import process_post  # Engineer B's module
        return process_post
    except ImportError as exc:
        logger.error(
            "Could not import pipeline.processor.process_post — "
            "is Engineer B's code deployed? Error: %s", exc
        )
        raise


# ---------------------------------------------------------------------------
# 1. Scheduler setup
# ---------------------------------------------------------------------------

def setup_scheduler(store) -> BackgroundScheduler:
    """
    Read all active projects from SQLite and register APScheduler jobs.

    Each source entry in a project's sources list looks like:
        {
            "type":       "reddit",
            "subreddits": ["ozempic", "diabetes"],   # reddit-specific
            "latency":    "realtime"                 # realtime | daily | weekly
        }

    Returns a started BackgroundScheduler.
    """
    executors = {
        # Each crawler.crawl() runs in its own thread — up to 10 concurrent
        "default": ThreadPoolExecutor(max_workers=10),
    }
    job_defaults = {
        "coalesce":       True,   # if a job is still running, skip the next fire
        "max_instances":  1,      # never run the same job twice simultaneously
        "misfire_grace_time": 120,
    }

    scheduler = BackgroundScheduler(
        executors=executors,
        job_defaults=job_defaults,
        timezone="UTC",
    )

    projects = get_active_projects()
    if not projects:
        logger.warning(
            "No active projects found in SQLite. "
            "Run scripts/seed_data.py to create demo projects."
        )

    registered = 0

    for project in projects:
        project_id = project["id"]
        keywords   = project["keywords"]
        sources    = project["sources"]

        logger.info(
            "Registering jobs for project %d (%s) — %d source(s).",
            project_id, project.get("name", "unnamed"), len(sources),
        )

        for source_cfg in sources:
            source_type = source_cfg.get("type", "").lower()
            latency     = source_cfg.get("latency", "daily").lower()

            crawler_cls = CRAWLER_CLASSES.get(source_type)
            if crawler_cls is None:
                logger.warning(
                    "Unknown source type %r in project %d — skipping.",
                    source_type, project_id,
                )
                continue

            # Build the crawler instance for this project+source combination.
            # Pass store so RedditCrawler can persist seen IDs across restarts.
            try:
                crawler = crawler_cls(
                    source_config=source_cfg,
                    keywords=keywords,
                    post_queue=POST_QUEUE,
                    sqlite_store=store,
                )
            except Exception as exc:
                logger.error(
                    "Failed to instantiate %s for project %d: %s",
                    crawler_cls.__name__, project_id, exc,
                )
                continue

            job_id = f"{source_type}_project{project_id}"
            _register_job(scheduler, crawler, latency, job_id)
            registered += 1

    logger.info("Scheduler: %d job(s) registered.", registered)
    scheduler.start()
    logger.info("Scheduler started.")
    return scheduler


def _register_job(
    scheduler: BackgroundScheduler,
    crawler,
    latency: str,
    job_id: str,
) -> None:
    """
    Add one APScheduler job for a crawler instance.

    Latency modes (from spec):
        realtime → interval, every 5 minutes
        daily    → cron, midnight UTC
        weekly   → cron, Sunday midnight UTC
    """
    if latency == "realtime":
        scheduler.add_job(
            crawler.crawl,
            trigger="interval",
            minutes=5,
            id=job_id,
            name=f"{job_id} (realtime)",
            # Fire immediately on startup so we don't wait 5min for first data
            next_run_time=datetime.now(timezone.utc),
        )
        logger.info("  [realtime] %s — every 5 minutes.", job_id)

    elif latency == "daily":
        scheduler.add_job(
            crawler.crawl,
            trigger="cron",
            hour=0,
            minute=0,
            id=job_id,
            name=f"{job_id} (daily)",
        )
        logger.info("  [daily] %s — midnight UTC.", job_id)

    elif latency == "weekly":
        scheduler.add_job(
            crawler.crawl,
            trigger="cron",
            day_of_week="sun",
            hour=0,
            minute=0,
            id=job_id,
            name=f"{job_id} (weekly)",
        )
        logger.info("  [weekly] %s — Sunday midnight UTC.", job_id)

    else:
        # Unknown latency — default to daily and warn
        logger.warning(
            "Unknown latency %r for job %s — defaulting to daily.", latency, job_id
        )
        scheduler.add_job(
            crawler.crawl,
            trigger="cron",
            hour=0,
            minute=0,
            id=job_id,
            name=f"{job_id} (daily-fallback)",
        )


# ---------------------------------------------------------------------------
# 2. Pipeline worker thread
# ---------------------------------------------------------------------------

def pipeline_worker(store) -> None:
    """
    Long-running thread. Reads RawPost dicts from POST_QUEUE one at a time,
    processes them into genomes, stores them (SQLite + ChromaDB),
    and pushes them to the API.

    Runs until SHUTDOWN is set, draining the queue before exiting.
    """
    logger.info("Pipeline worker thread started.")

    process_post = None  # lazy load

    while not SHUTDOWN.is_set():
        try:
            raw_post = POST_QUEUE.get(timeout=1.0)
        except queue.Empty:
            continue

        try:
            source = raw_post.get("source", "unknown")
            logger.info(
                "Processing post from %s (queue depth: %d)",
                source, POST_QUEUE.qsize()
            )

            # Lazy-load pipeline
            if process_post is None:
                logger.info("Loading Engineer B's pipeline (first post)...")
                process_post = _get_pipeline()
                logger.info("Pipeline loaded.")

            # --- Engineer B processing ---
            genome = process_post(raw_post)

            if genome is None:
                logger.debug(
                    "No signal detected in post from %s — skipping.", source
                )
                continue

            # --- Persist to SQLite ---
            project_id = genome.get("project_id") or _infer_project_id(raw_post)
            saved = save_genome(genome, project_id)

            if saved:
                logger.info(
                    "Genome saved: %s | signal=%s | drug=%s | severity=%s",
                    genome.get("post_id", "?"),
                    genome.get("signal_type", "?"),
                    genome.get("drug", "?"),
                    genome.get("severity", "?"),
                )

                # --- NEW: Store in ChromaDB ---
                try:
                    from storage.chroma_store import store_genome_vector
                    store_genome_vector(genome)
                except Exception as e:
                    logger.warning("ChromaDB store failed: %s", e)

            # --- Push to API (broadcast endpoint) ---
            try:
                import httpx
                httpx.post(
                    "http://localhost:8000/internal/broadcast",
                    json=genome if isinstance(genome, dict) else genome.to_dict(),
                    timeout=2.0
                )
            except Exception as e:
                logger.warning("Broadcast failed: %s", e)

        except Exception as exc:
            logger.error(
                "Pipeline error on post %s: %s",
                raw_post.get("post_id", "?"),
                exc,
                exc_info=True,
            )
        finally:
            POST_QUEUE.task_done()

    # --- Shutdown handling ---
    logger.info(
        "Shutdown signal received — draining queue (%d items)...",
        POST_QUEUE.qsize()
    )
    _drain_queue(process_post, store)
    logger.info("Pipeline worker thread exited.")


def _drain_queue(process_post, store) -> None:
    """
    Process remaining items in the queue after SHUTDOWN is set.
    Gives the pipeline a clean exit rather than dropping in-flight posts.
    Stops after 30s regardless to avoid hanging the container shutdown.
    """
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            raw_post = POST_QUEUE.get_nowait()
        except queue.Empty:
            break
        try:
            if process_post is not None:
                genome = process_post(raw_post)
                if genome:
                    project_id = genome.get("project_id") or _infer_project_id(raw_post)
                    save_genome(genome, project_id)
                    _push_genome_to_api(genome)
        except Exception as exc:
            logger.error("Drain error: %s", exc)
        finally:
            POST_QUEUE.task_done()


# ---------------------------------------------------------------------------
# 3. WebSocket / HTTP push to Engineer C's API
# ---------------------------------------------------------------------------

def _push_genome_to_api(genome: dict) -> None:
    """
    POST the genome dict to Engineer C's internal HTTP endpoint.
    The FastAPI service then fans it out to connected WebSocket clients.

    Uses a short timeout — if the API is down, log and move on.
    Never block the pipeline thread waiting for the API.
    """
    try:
        resp = requests.post(
            WS_PUSH_URL,
            json=genome,
            timeout=3,
        )
        if resp.status_code not in (200, 201, 202):
            logger.warning(
                "API push returned %d for genome %s.",
                resp.status_code, genome.get("post_id", "?"),
            )
    except requests.exceptions.ConnectionError:
        # API service not up yet (common on fresh docker compose up)
        logger.debug("API not reachable — genome %s not pushed (will retry next post).",
                     genome.get("post_id", "?"))
    except requests.exceptions.Timeout:
        logger.warning("API push timed out for genome %s.", genome.get("post_id", "?"))
    except Exception as exc:
        logger.error("API push failed: %s", exc)


# ---------------------------------------------------------------------------
# 4. Helpers
# ---------------------------------------------------------------------------

def _infer_project_id(raw_post: dict) -> int:
    """
    Fallback project_id when Engineer B's genome doesn't include one.
    In the demo, project 1 = Ozempic, project 2 = cough syrup.
    Infer from source string — not perfect but safe for hackathon.
    """
    source = raw_post.get("source", "").lower()
    ozempic_signals = {"ozempic", "diabetes", "loseit", "semaglutide"}
    if any(sig in source for sig in ozempic_signals):
        return 1
    return 2


def _build_store():
    """
    Import and return the SQLite store module.
    Kept as a function so it's clear what engineer A's store is.
    """
    import storage.sqlite_store as store
    return store


# ---------------------------------------------------------------------------
# 5. Graceful shutdown
# ---------------------------------------------------------------------------

def _handle_shutdown(signum, frame):
    """SIGINT / SIGTERM handler — sets the event that stops all threads."""
    logger.info("Shutdown signal (%d) received — stopping...", signum)
    SHUTDOWN.set()


# ---------------------------------------------------------------------------
# 6. Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("=" * 60)
    logger.info("Starting Patient Safety Sentinel pipeline worker...")
    logger.info("=" * 60)

    # Register signal handlers for clean Docker shutdown (SIGTERM) and Ctrl+C
    signal.signal(signal.SIGINT,  _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    # --- Initialize database ---
    logger.info("Initializing database...")
    init_db()

    # --- Store reference (passed to crawlers + pipeline thread) ---
    store = _build_store()

    # --- Start pipeline consumer thread ---
    pipeline_thread = threading.Thread(
        target=pipeline_worker,
        args=(store,),
        name="pipeline-worker",
        daemon=False,   # non-daemon so drain_queue runs on shutdown
    )
    pipeline_thread.start()

    # --- Register and start APScheduler jobs ---
    scheduler = setup_scheduler(store)

    logger.info("Worker running. Press Ctrl+C to stop.")

    # --- Main loop — just keeps the process alive ---
    try:
        while not SHUTDOWN.is_set():
            time.sleep(1)
    finally:
        logger.info("Stopping scheduler...")
        scheduler.shutdown(wait=False)

        logger.info("Waiting for pipeline thread to drain...")
        pipeline_thread.join(timeout=35)

        if pipeline_thread.is_alive():
            logger.warning("Pipeline thread did not exit cleanly — forcing.")

        logger.info("Worker stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()