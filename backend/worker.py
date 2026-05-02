"""
worker.py — Background pipeline worker
OWNER: Engineer A

This process:
1. Runs the APScheduler for all latency modes
2. Pulls posts from the queue
3. Sends each post through the processing pipeline
4. Stores resulting genomes
5. Pushes to WebSocket via internal HTTP call
"""
import time
import queue
import threading
import logging
from apscheduler.schedulers.background import BackgroundScheduler

from crawlers.reddit import RedditCrawler
from crawlers.twitter import TwitterCrawler
from crawlers.forum import ForumCrawler
from crawlers.rss import RSSCrawler
from pipeline.processor import PipelineProcessor
from storage.sqlite_store import get_active_projects

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("worker")

# Shared in-memory queue between crawlers and pipeline
post_queue: queue.Queue = queue.Queue(maxsize=1000)

def pipeline_worker():
    """Continuously processes posts from the queue."""
    processor = PipelineProcessor()
    while True:
        try:
            raw_post = post_queue.get(timeout=5)
            log.info(f"Processing post from {raw_post.get('source')}")
            genome = processor.process(raw_post)
            if genome:
                # TODO Engineer B: plug in outbreak detector here
                # TODO Engineer C: push genome to WebSocket manager
                log.info(f"Genome created: {genome.genome_id}")
            post_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            log.error(f"Pipeline error: {e}")

def setup_scheduler():
    """Register all crawl jobs based on project configs."""
    scheduler = BackgroundScheduler()
    projects = get_active_projects()

    for project in projects:
        for source_config in project.get("sources", []):
            source_type = source_config["type"]
            latency    = source_config["latency"]   # realtime | daily | weekly
            keywords   = project["keywords"]

            crawler_map = {
                "reddit":  RedditCrawler,
                "twitter": TwitterCrawler,
                "forum":   ForumCrawler,
                "rss":     RSSCrawler,
            }
            CrawlerClass = crawler_map.get(source_type)
            if not CrawlerClass:
                continue

            crawler = CrawlerClass(source_config, keywords, post_queue)

            if latency == "realtime":
                scheduler.add_job(crawler.crawl, "interval", minutes=5,
                                  id=f"{project['id']}_{source_type}_rt")
            elif latency == "daily":
                scheduler.add_job(crawler.crawl, "cron", hour=0,
                                  id=f"{project['id']}_{source_type}_daily")
            elif latency == "weekly":
                scheduler.add_job(crawler.crawl, "cron", day_of_week="sun", hour=0,
                                  id=f"{project['id']}_{source_type}_weekly")

    scheduler.start()
    return scheduler

if __name__ == "__main__":
    log.info("Starting pipeline worker...")
    scheduler = setup_scheduler()
    t = threading.Thread(target=pipeline_worker, daemon=True)
    t.start()
    log.info("Worker running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.shutdown()
        log.info("Worker stopped.")
