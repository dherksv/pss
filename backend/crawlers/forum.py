"""
forum.py - Generic forum crawler | OWNER: Engineer A
Extensible: add new forum URLs in project config, no code changes needed
"""
import requests
from bs4 import BeautifulSoup
from .base import BaseCrawler, make_raw_post

class ForumCrawler(BaseCrawler):
    def crawl(self):
        urls      = self.config.get("urls", [])
        selectors = self.config.get("selectors", {"post": ".post-body"})
        for url in urls:
            try:
                soup = BeautifulSoup(
                    requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"}).text,
                    "html.parser")
                for el in soup.select(selectors.get("post", "p"))[:20]:
                    text = el.get_text(" ", strip=True)
                    if any(kw.lower() in text.lower() for kw in self.keywords):
                        self._enqueue(make_raw_post(
                            source=url, source_type="forum", text=text, url=url,
                            metadata={"forum_url": url}))
            except Exception as e:
                print(f"Forum error [{url}]: {e}")
