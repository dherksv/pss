"""
backend/crawlers/forum.py

Forum crawler for Patient Safety Sentinel.
Uses requests + BeautifulSoup4 for CSS-selector-driven scraping.

Design principle — extensible with zero code changes:
    New forums are added purely via project config (CSS selectors + URL).
    No forum-specific logic lives in this file.

Config format (source_config):
    {
        "type": "forum",
        "urls": [
            "https://patientforum.example.com/diabetes",
            "https://healthboards.com/boards/diabetes"
        ],
        "selectors": {
            "post":   ".post-body",       # container wrapping each post
            "title":  ".post-title",      # optional — post title inside container
            "author": ".post-author"      # optional — author inside container
        }
    }

Fallback selectors used when config selectors are missing or match nothing.
"""

import logging
import queue
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .base import BaseCrawler, make_raw_post

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default CSS selectors — broad patterns that work across most forum software
# (phpBB, vBulletin, Discourse, XenForo, plain HTML boards)
# ---------------------------------------------------------------------------
DEFAULT_SELECTORS = {
    "post": (
        # Discourse
        ".topic-post .cooked, "
        # phpBB
        ".post .content, "
        # vBulletin
        ".postbody .restore, "
        # XenForo
        ".message-body .bbWrapper, "
        # Generic fallback — any element with 'post' in its class
        "[class*='post-body'], [class*='post_body'], "
        "[class*='post-content'], [class*='post_content']"
    ),
    "title": (
        ".post-title, .topic-title, "
        "h1.title, h2.title, h3.title, "
        "[class*='post-title'], [class*='thread-title']"
    ),
    "author": (
        ".post-author, .username, .author, "
        "[class*='post-author'], [class*='user-name'], "
        "[itemprop='name']"
    ),
}

# Request headers — realistic browser UA to avoid 403 blocks
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "DNT":             "1",
    "Connection":      "keep-alive",
}

REQUEST_TIMEOUT  = 10    # seconds per page fetch
SEEN_IDS_CAP     = 10_000


class ForumCrawler(BaseCrawler):
    """
    Scrapes forum pages for healthcare safety signals.

    Config keys expected in source_config:
        urls      (list)          — forum page URLs to scrape
        selectors (dict, optional) — CSS selectors for post/title/author

    Optional:
        sqlite_store — for persistent dedup across container restarts
    """

    def __init__(
        self,
        source_config: dict,
        keywords: list,
        post_queue: queue.Queue,
        sqlite_store=None,
    ):
        super().__init__(source_config, keywords, post_queue)

        self._store    = sqlite_store
        self._seen_ids: set[str] = set()

        self._urls: list[str] = source_config.get("urls", [])

        # Merge config selectors over defaults — config wins per key
        cfg_selectors = source_config.get("selectors", {})
        self._selectors = {**DEFAULT_SELECTORS, **cfg_selectors}

        # Lowercase keywords once for fast matching
        self._keywords_lower = [kw.lower() for kw in self.keywords]

        # Reuse HTTP session across pages — keeps TCP connections alive
        self._session = requests.Session()
        self._session.headers.update(REQUEST_HEADERS)

        if not self._urls:
            logger.warning(
                "ForumCrawler: no URLs configured — crawl() will no-op."
            )

        # Load persisted seen IDs
        if self._store is not None:
            try:
                persisted = self._store.get_seen_post_ids(source="forum")
                self._seen_ids.update(persisted)
                logger.info(
                    "Loaded %d persisted forum post IDs from SQLite cache.",
                    len(persisted),
                )
            except Exception as exc:
                logger.warning("Could not load persisted forum IDs: %s", exc)

    # -----------------------------------------------------------------------
    # Public API — called by APScheduler
    # -----------------------------------------------------------------------

    def crawl(self) -> None:
        """
        Scrape every configured URL. Filter posts by keyword presence.
        Enqueue matching posts as RawPost dicts.
        """
        if not self._urls:
            logger.warning("ForumCrawler: no URLs configured — skipping crawl.")
            return

        logger.info(
            "ForumCrawler: starting crawl — %d URL(s), %d keyword(s).",
            len(self._urls), len(self.keywords),
        )

        total_enqueued = 0

        for url in self._urls:
            try:
                enqueued = self._crawl_page(url)
                total_enqueued += enqueued
            except Exception as exc:
                logger.error(
                    "ForumCrawler: unhandled error on %s: %s",
                    url, exc, exc_info=True,
                )

        logger.info(
            "ForumCrawler: crawl complete — %d new post(s) enqueued.",
            total_enqueued,
        )

    # -----------------------------------------------------------------------
    # Per-page scraping
    # -----------------------------------------------------------------------

    def _crawl_page(self, url: str) -> int:
        """
        Fetch and parse one forum page. Returns count of posts enqueued.
        """
        html = self._fetch_page(url)
        if html is None:
            return 0

        soup = BeautifulSoup(html, "html.parser")
        post_containers = soup.select(self._selectors["post"])

        if not post_containers:
            # Selector matched nothing — log clearly so config can be fixed
            logger.warning(
                "ForumCrawler: post selector %r matched 0 elements on %s. "
                "Check 'selectors.post' in project config.",
                self._selectors["post"], url,
            )
            return 0

        logger.debug(
            "ForumCrawler: %d post container(s) found on %s.",
            len(post_containers), url,
        )

        enqueued = 0

        for container in post_containers:
            title  = self._extract_field(container, "title")
            author = self._extract_field(container, "author")
            body   = container.get_text(separator=" ", strip=True)

            # Combine title + body for keyword matching and RawPost text
            full_text = f"{title}\n{body}".strip() if title else body

            # Skip posts with no meaningful content
            if not full_text or len(full_text) < 10:
                continue

            # Keyword filter — only enqueue relevant posts
            if not self._matches_keywords(full_text):
                continue

            # Build a stable ID from URL + content fingerprint
            post_id = self._make_post_id(url, full_text)

            if self._is_seen(post_id):
                continue
            self._mark_seen(post_id)

            raw = self._build_raw_post(
                text=full_text,
                url=url,
                author=author or None,
                forum_url=url,
            )
            self._enqueue(raw)
            enqueued += 1

        if enqueued:
            logger.info(
                "ForumCrawler: %s → %d new post(s) enqueued.", url, enqueued
            )

        return enqueued

    # -----------------------------------------------------------------------
    # HTTP fetch
    # -----------------------------------------------------------------------

    def _fetch_page(self, url: str) -> str | None:
        """
        Fetch a forum page. Returns HTML string or None on any failure.
        All errors caught — one broken URL never aborts the crawl cycle.
        """
        try:
            resp = self._session.get(url, timeout=REQUEST_TIMEOUT)

            if resp.status_code == 403:
                logger.warning(
                    "ForumCrawler: 403 Forbidden on %s — "
                    "site may block scrapers. Try adding cookies to config.", url,
                )
                return None

            if resp.status_code == 404:
                logger.warning("ForumCrawler: 404 Not Found — %s", url)
                return None

            if resp.status_code == 429:
                logger.warning(
                    "ForumCrawler: 429 rate limited on %s — skipping this cycle.", url
                )
                return None

            resp.raise_for_status()

            # Detect encoding — requests uses chardet if charset missing
            resp.encoding = resp.apparent_encoding
            return resp.text

        except requests.exceptions.Timeout:
            logger.warning(
                "ForumCrawler: timeout after %ds on %s — skipping.",
                REQUEST_TIMEOUT, url,
            )
            return None

        except requests.exceptions.TooManyRedirects:
            logger.warning("ForumCrawler: too many redirects on %s — skipping.", url)
            return None

        except requests.exceptions.ConnectionError as exc:
            logger.error("ForumCrawler: connection error on %s: %s", url, exc)
            return None

        except Exception as exc:
            logger.error(
                "ForumCrawler: unexpected fetch error on %s: %s", url, exc
            )
            return None

    # -----------------------------------------------------------------------
    # Field extraction
    # -----------------------------------------------------------------------

    def _extract_field(self, container: BeautifulSoup, field: str) -> str:
        """
        Extract a text field (title or author) from within a post container.
        Returns empty string if selector matches nothing — never raises.
        """
        selector = self._selectors.get(field, "")
        if not selector:
            return ""
        try:
            el = container.select_one(selector)
            if el:
                return el.get_text(separator=" ", strip=True)
        except Exception as exc:
            logger.debug(
                "ForumCrawler: selector %r failed on field %r: %s",
                selector, field, exc,
            )
        return ""

    # -----------------------------------------------------------------------
    # RawPost builder
    # -----------------------------------------------------------------------

    def _build_raw_post(
        self,
        text: str,
        url: str,
        author: str | None,
        forum_url: str,
    ) -> dict:
        """
        Convert scraped post data → RawPost via make_raw_post().
        NEVER construct the dict manually — always use the helper.
        """
        # Use forum domain as human-readable source label
        domain = urlparse(url).netloc or url

        return make_raw_post(
            source      = f"forum/{domain}",
            source_type = "forum",
            text        = text,
            url         = url,
            author      = author,
            timestamp   = datetime.now(timezone.utc).isoformat(),
            metadata    = {
                "forum_url": forum_url,
            },
        )

    # -----------------------------------------------------------------------
    # Keyword matching
    # -----------------------------------------------------------------------

    def _matches_keywords(self, text: str) -> bool:
        """
        Return True if any project keyword appears in the post text.
        Case-insensitive substring match.
        """
        text_lower = text.lower()
        return any(kw in text_lower for kw in self._keywords_lower)

    # -----------------------------------------------------------------------
    # Deduplication
    # -----------------------------------------------------------------------

    def _make_post_id(self, url: str, text: str) -> str:
        """
        Build a stable dedup key for a forum post.

        Forum posts rarely have stable IDs in their HTML — we fingerprint
        using a hash of the page URL + first 200 chars of post text.
        Collision probability is negligible at hackathon scale.
        """
        import hashlib
        fingerprint = f"{url}::{text[:200]}"
        return hashlib.sha1(fingerprint.encode("utf-8", errors="replace")).hexdigest()

    def _is_seen(self, post_id: str) -> bool:
        if post_id in self._seen_ids:
            return True
        if self._store is not None:
            try:
                return self._store.is_post_seen(post_id, source="forum")
            except Exception:
                pass
        return False

    def _mark_seen(self, post_id: str) -> None:
        if len(self._seen_ids) >= SEEN_IDS_CAP:
            logger.info("ForumCrawler: _seen_ids cap hit — clearing.")
            self._seen_ids.clear()
        self._seen_ids.add(post_id)
        if self._store is not None:
            try:
                self._store.mark_post_seen(post_id, source="forum")
            except Exception as exc:
                logger.warning(
                    "Could not persist forum seen ID %s: %s", post_id, exc
                )