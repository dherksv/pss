"""
rss.py - RSS feed crawler | OWNER: Engineer A
Includes FDA MedWatch feed — new drug approvals trigger Source Discovery Agent
"""
import feedparser
from .base import BaseCrawler, make_raw_post

DEFAULT_FEEDS = [
    "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/medwatch-safety-alerts/rss.xml",
    "https://www.who.int/rss-feeds/news-english.xml",
    "https://feeds.reuters.com/reuters/healthNews",
]

class RSSCrawler(BaseCrawler):
    def crawl(self):
        for feed_url in self.config.get("feeds", DEFAULT_FEEDS):
            try:
                for entry in feedparser.parse(feed_url).entries[:20]:
                    text = f"{entry.get('title','')} {entry.get('summary','')}"
                    if any(kw.lower() in text.lower() for kw in self.keywords):
                        self._enqueue(make_raw_post(
                            source=feed_url, source_type="rss", text=text,
                            url=entry.get("link", feed_url),
                            timestamp=entry.get("published", ""),
                            metadata={"is_fda": "fda.gov" in feed_url}))
            except Exception as e:
                print(f"RSS error [{feed_url}]: {e}")
