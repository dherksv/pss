"""
backend/crawlers/rss.py

RSS/Atom feed crawler for Patient Safety Sentinel.
Uses feedparser — handles all RSS 1.0, RSS 2.0, and Atom format variations.

Special behaviour:
    - FDA MedWatch feed entries are flagged with is_fda=True in metadata
    - FDA entries ideally trigger Engineer B's source discovery agent
    - Default feeds always monitored regardless of project config
    - Project config may add extra feeds on top of defaults
    - Keyword filtering applied before enqueue — only relevant entries queued
"""

import logging
import queue
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

from .base import BaseCrawler, make_raw_post

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default feeds — always monitored for every project
# ---------------------------------------------------------------------------
DEFAULT_FEEDS = [
    # FDA MedWatch safety alerts — critical for demo
    "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/medwatch-safety-alerts/rss.xml",
    # WHO news
    "https://www.who.int/rss-feeds/news-english.xml",
    # Reuters health
    "https://feeds.reuters.com/reuters/healthNews",
]

# FDA feed URL substring — used to detect and flag FDA entries
FDA_FEED_MARKER = "fda.gov"

# In-memory dedup cap
SEEN_IDS_CAP = 10_000


class RSSCrawler(BaseCrawler):
    """
    Crawls RSS/Atom feeds for healthcare safety signals.

    Config keys expected in source_config:
        feeds (list, optional) — extra feed URLs beyond DEFAULT_FEEDS

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

        self._store = sqlite_store
        self._seen_ids: set[str] = set()

        # Merge default feeds with any project-specific extras
        extra_feeds = source_config.get("feeds", [])
        self._feeds: list[str] = list(dict.fromkeys(
            DEFAULT_FEEDS + [f for f in extra_feeds if f not in DEFAULT_FEEDS]
        ))

        # Lowercase keywords once for fast case-insensitive matching
        self._keywords_lower = [kw.lower() for kw in self.keywords]

        # Load persisted seen IDs from SQLite
        if self._store is not None:
            try:
                persisted = self._store.get_seen_post_ids(source="rss")
                self._seen_ids.update(persisted)
                logger.info(
                    "Loaded %d persisted RSS entry IDs from SQLite cache.",
                    len(persisted),
                )
            except Exception as exc:
                logger.warning("Could not load persisted RSS IDs: %s", exc)

    # -----------------------------------------------------------------------
    # Public API — called by APScheduler
    # -----------------------------------------------------------------------

    def crawl(self) -> None:
        """
        Parse every configured feed, filter entries by keyword presence,
        and enqueue matching entries as RawPost dicts.
        """
        logger.info(
            "RSSCrawler: starting crawl — %d feed(s), %d keyword(s).",
            len(self._feeds), len(self.keywords),
        )

        total_enqueued = 0

        for feed_url in self._feeds:
            try:
                enqueued = self._crawl_feed(feed_url)
                total_enqueued += enqueued
            except Exception as exc:
                # Never let one broken feed abort the rest
                logger.error(
                    "RSSCrawler: unhandled error on feed %s: %s",
                    feed_url, exc, exc_info=True,
                )

        logger.info("RSSCrawler: crawl complete — %d new entry(s) enqueued.", total_enqueued)

    # -----------------------------------------------------------------------
    # Per-feed logic
    # -----------------------------------------------------------------------

    def _crawl_feed(self, feed_url: str) -> int:
        """
        Fetch and parse one feed. Returns count of entries enqueued.
        feedparser never raises — it returns a bozo flag on parse errors.
        """
        logger.debug("RSSCrawler: fetching %s", feed_url)

        parsed = feedparser.parse(
            feed_url,
            agent="PatientSafetySentinel/1.0 (+https://github.com/your-org/sentinel)",
            # feedparser respects ETags and Last-Modified automatically
            # when the feed_url is re-fetched — saves bandwidth
        )

        # feedparser sets bozo=True on malformed feeds but still returns
        # whatever it could parse — log the exception but continue
        if parsed.bozo:
            bozo_exc = parsed.get("bozo_exception", "unknown")
            logger.warning(
                "RSSCrawler: feed %s is malformed (%s) — "
                "processing partial results.", feed_url, bozo_exc,
            )

        entries = parsed.get("entries", [])
        if not entries:
            logger.debug("RSSCrawler: no entries in %s", feed_url)
            return 0

        is_fda = FDA_FEED_MARKER in feed_url.lower()
        feed_title = parsed.feed.get("title", feed_url)
        enqueued = 0

        for entry in entries:
            entry_id = self._get_entry_id(entry, feed_url)

            # --- Dedup ---
            if self._is_seen(entry_id):
                continue

            # --- Build combined text for keyword matching ---
            text = self._extract_text(entry)

            # --- Keyword filter — only enqueue relevant entries ---
            if not self._matches_keywords(text):
                # FDA entries are always enqueued regardless of keyword match
                # because a new drug approval may introduce keywords we don't
                # know yet — Engineer B's source discovery handles them
                if not is_fda:
                    continue

            self._mark_seen(entry_id)

            raw = self._build_raw_post(
                entry=entry,
                text=text,
                feed_url=feed_url,
                feed_title=feed_title,
                is_fda=is_fda,
            )
            self._enqueue(raw)
            enqueued += 1

            if is_fda:
                logger.info(
                    "FDA MedWatch entry enqueued: %s",
                    entry.get("title", "untitled"),
                )

        if enqueued:
            logger.info(
                "RSSCrawler: %s → %d new entry(s) enqueued.", feed_title, enqueued
            )

        return enqueued

    # -----------------------------------------------------------------------
    # RawPost builder
    # -----------------------------------------------------------------------

    def _build_raw_post(
        self,
        entry: dict,
        text: str,
        feed_url: str,
        feed_title: str,
        is_fda: bool,
    ) -> dict:
        """
        Convert a feedparser entry → RawPost via make_raw_post().
        NEVER construct the dict manually — always use the helper.
        """
        url    = entry.get("link", feed_url)
        author = entry.get("author") or entry.get("author_detail", {}).get("name")
        ts     = self._parse_timestamp(entry)

        return make_raw_post(
            source      = f"rss/{feed_title}",
            source_type = "rss",
            text        = text,
            url         = url,
            author      = author,
            timestamp   = ts,
            metadata    = {
                "feed":   feed_url,
                "is_fda": is_fda,
            },
        )

    # -----------------------------------------------------------------------
    # Text extraction
    # -----------------------------------------------------------------------

    def _extract_text(self, entry) -> str:
        """
        Extract the richest available text from a feedparser entry.

        Priority: content (full body) → summary → title
        Strips HTML tags using feedparser's html_to_text helper
        so Engineer B receives clean plain text.
        """
        # feedparser normalizes content into entry.content (a list of dicts)
        content_list = entry.get("content", [])
        if content_list:
            raw = content_list[0].get("value", "")
            if raw:
                return _strip_html(raw)

        summary = entry.get("summary", "")
        if summary:
            return _strip_html(summary)

        return entry.get("title", "")

    # -----------------------------------------------------------------------
    # Keyword matching
    # -----------------------------------------------------------------------

    def _matches_keywords(self, text: str) -> bool:
        """
        Return True if any project keyword appears in the entry text.
        Case-insensitive. O(n_keywords) — fine at hackathon scale.
        """
        text_lower = text.lower()
        return any(kw in text_lower for kw in self._keywords_lower)

    # -----------------------------------------------------------------------
    # Deduplication
    # -----------------------------------------------------------------------

    def _get_entry_id(self, entry, feed_url: str) -> str:
        """
        Build a stable dedup key for a feed entry.

        Priority:
            1. entry.id   (guid in RSS, id in Atom) — most reliable
            2. entry.link — stable for most feeds
            3. feed_url + title hash — last resort
        """
        if entry.get("id"):
            return entry["id"]
        if entry.get("link"):
            return entry["link"]
        # Fallback — combine feed URL and title into a stable string
        title = entry.get("title", "")
        return f"{feed_url}::{title}"

    def _is_seen(self, entry_id: str) -> bool:
        if entry_id in self._seen_ids:
            return True
        if self._store is not None:
            try:
                return self._store.is_post_seen(entry_id, source="rss")
            except Exception:
                pass
        return False

    def _mark_seen(self, entry_id: str) -> None:
        if len(self._seen_ids) >= SEEN_IDS_CAP:
            logger.info("RSSCrawler: _seen_ids cap hit — clearing.")
            self._seen_ids.clear()
        self._seen_ids.add(entry_id)
        if self._store is not None:
            try:
                self._store.mark_post_seen(entry_id, source="rss")
            except Exception as exc:
                logger.warning(
                    "Could not persist RSS seen ID %s: %s", entry_id, exc
                )

    # -----------------------------------------------------------------------
    # Timestamp parsing
    # -----------------------------------------------------------------------

    @staticmethod
    def _parse_timestamp(entry) -> str:
        """
        Extract publish timestamp from a feedparser entry → ISO8601 string.

        feedparser normalises dates into entry.published_parsed (a time.struct_time
        in UTC) when it can parse them. Falls back to entry.updated_parsed,
        then entry.published (raw string), then now.
        """
        # published_parsed / updated_parsed are time.struct_time in UTC
        for attr in ("published_parsed", "updated_parsed"):
            t = entry.get(attr)
            if t is not None:
                try:
                    dt = datetime(*t[:6], tzinfo=timezone.utc)
                    return dt.isoformat()
                except Exception:
                    pass

        # Raw published string — try RFC 2822 (email date format used by RSS)
        raw = entry.get("published") or entry.get("updated", "")
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                return dt.astimezone(timezone.utc).isoformat()
            except Exception:
                pass

        return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# HTML stripper — module-level utility
# ---------------------------------------------------------------------------

def _strip_html(html: str) -> str:
    """
    Remove HTML tags from feed content to give Engineer B clean plain text.
    Uses Python stdlib html.parser — no extra dependencies.
    Preserves whitespace between block elements for readability.
    """
    from html.parser import HTMLParser

    class _Stripper(HTMLParser):
        # Block-level tags that should become newlines
        BLOCK_TAGS = {
            "p", "br", "div", "li", "tr", "h1", "h2",
            "h3", "h4", "h5", "h6", "blockquote",
        }

        def __init__(self):
            super().__init__()
            self._parts: list[str] = []

        def handle_data(self, data: str):
            stripped = data.strip()
            if stripped:
                self._parts.append(stripped)

        def handle_starttag(self, tag, attrs):
            if tag.lower() in self.BLOCK_TAGS:
                self._parts.append(" ")

        def get_text(self) -> str:
            return " ".join(self._parts).strip()

    stripper = _Stripper()
    stripper.feed(html)
    return stripper.get_text()