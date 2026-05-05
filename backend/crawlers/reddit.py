"""
backend/crawlers/reddit.py

Reddit crawler for Patient Safety Sentinel.
Strategy: PRAW (authenticated) primary → Reddit .json endpoint fallback on 429/auth failure.
Deduplication: in-memory _seen_ids (fast, per-cycle) + SQLite crawl_cache (persistent across restarts).
"""

import logging
import queue
import time
from datetime import datetime, timezone

import praw
import prawcore
import requests

from .base import BaseCrawler, make_raw_post

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Geographic proxy — subreddit name → ISO region code
# Used to populate metadata.geo_proxy for Engineer B's signal genome pipeline
# ---------------------------------------------------------------------------
GEO_MAP = {
    "india":          "IN",
    "mumbai":         "IN-MH",
    "kerala":         "IN-KL",
    "chennai":        "IN-TN",
    "delhi":          "IN-DL",
    "unitedkingdom":  "GB",
    "australia":      "AU",
    "canada":         "CA",
    # demo scenario subreddits (no specific region → None, handled below)
    "ozempic":        None,
    "diabetes":       None,
    "loseit":         None,
    "askdocs":        None,
    "chronicillness": None,
    "parenting":      None,
    "medicine":       None,
    "mildlyinfuriating": None,
}

# Max posts fetched per keyword per subreddit per crawl cycle (per spec)
POSTS_PER_SEARCH = 25

# In-memory dedup cap — clear when set exceeds this to prevent memory growth
SEEN_IDS_CAP = 10_000

# Seconds to wait before retrying after a rate-limit hit
DEFAULT_BACKOFF = 60  # overridden by Retry-After header when present

# User-Agent for .json fallback requests
_JSON_UA = "PatientSafetySentinel/1.0 (fallback; +https://github.com/your-org/sentinel)"


class RedditCrawler(BaseCrawler):
    """
    Crawls Reddit for healthcare safety signals.

    Config keys expected in source_config:
        client_id   (str)  — from REDDIT_CLIENT_ID env var
        secret      (str)  — from REDDIT_SECRET env var
        user_agent  (str)  — from REDDIT_USER_AGENT env var
        subreddits  (list) — eg ["ozempic", "diabetes", "loseit"]

    Optional:
        sqlite_store (SQLiteStore instance) — if provided, seen IDs are
                     persisted to the crawl_cache table across restarts.
    """

    def __init__(
        self,
        source_config: dict,
        keywords: list,
        post_queue: queue.Queue,
        sqlite_store=None,          # optional — pass store for persistent dedup
    ):
        super().__init__(source_config, keywords, post_queue)

        self._seen_ids: set[str] = set()
        self._store = sqlite_store
        self._praw_ok = True        # flips False if auth/init fails → use .json

        # --- Boot PRAW client ---
        try:
            self._reddit = praw.Reddit(
                client_id=source_config["client_id"],
                client_secret=source_config["secret"],
                user_agent=source_config.get(
                    "user_agent",
                    "PatientSafetySentinel/1.0 by sentinel-bot",
                ),
                # Read-only mode — no username/password needed for search
                read_only=True,
            )
            # Validate credentials with a cheap call
            _ = self._reddit.user.me()  # returns None in read-only, raises on bad creds
        except Exception as exc:
            logger.warning(
                "PRAW init failed (%s) — will use .json fallback for all requests.", exc
            )
            self._praw_ok = False

        # --- Load persisted seen IDs from SQLite (survive restarts) ---
        if self._store is not None:
            try:
                persisted = self._store.get_seen_post_ids(source="reddit")
                self._seen_ids.update(persisted)
                logger.info(
                    "Loaded %d persisted Reddit post IDs from SQLite cache.",
                    len(persisted),
                )
            except Exception as exc:
                logger.warning("Could not load persisted seen IDs: %s", exc)

    # -----------------------------------------------------------------------
    # Public API — called by APScheduler
    # -----------------------------------------------------------------------

    def crawl(self) -> None:
        """
        Main crawl entry point. Iterates every configured subreddit × keyword.
        Posts that pass dedup are enqueued as RawPost dicts.
        """
        subreddits: list[str] = self.config.get("subreddits", [])
        if not subreddits:
            logger.warning("RedditCrawler: no subreddits configured — skipping.")
            return

        logger.info(
            "RedditCrawler: starting crawl — %d subreddit(s), %d keyword(s).",
            len(subreddits),
            len(self.keywords),
        )

        for sub in subreddits:
            for keyword in self.keywords:
                try:
                    self._crawl_one(sub.lower().strip(), keyword)
                except Exception as exc:
                    # Never let one sub/keyword failure abort the whole cycle
                    logger.error(
                        "RedditCrawler: unhandled error on r/%s + %r: %s",
                        sub, keyword, exc, exc_info=True,
                    )

        logger.info("RedditCrawler: crawl cycle complete.")

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _crawl_one(self, subreddit: str, keyword: str) -> None:
        """Fetch posts for one subreddit+keyword pair."""
        if self._praw_ok:
            posts = self._fetch_via_praw(subreddit, keyword)
        else:
            posts = self._fetch_via_json(subreddit, keyword)

        enqueued = 0
        for post in posts:
            post_id = post.get("id")
            if not post_id:
                continue

            # --- Two-layer dedup ---
            if self._is_seen(post_id):
                continue
            self._mark_seen(post_id)

            raw = self._build_raw_post(post, subreddit)
            self._enqueue(raw)
            enqueued += 1

        if enqueued:
            logger.info(
                "r/%s | %r → enqueued %d new post(s).", subreddit, keyword, enqueued
            )

    def _fetch_via_praw(self, subreddit: str, keyword: str) -> list[dict]:
        """
        Fetch posts using PRAW (authenticated, respects rate limits automatically).
        Falls back to .json on TooManyRequests or any prawcore error.
        Returns a list of normalized post dicts.
        """
        results = []
        try:
            sub = self._reddit.subreddit(subreddit)
            for submission in sub.search(
                keyword,
                sort="new",
                time_filter="week",     # recent posts only — keeps results fresh
                limit=POSTS_PER_SEARCH,
            ):
                results.append(self._normalize_praw_post(submission))

        except prawcore.exceptions.TooManyRequests as exc:
            wait = self._parse_retry_after(exc) or DEFAULT_BACKOFF
            logger.warning(
                "PRAW 429 on r/%s — backing off %ds, then .json fallback.",
                subreddit, wait,
            )
            time.sleep(wait)
            # Flip to .json for the rest of this cycle
            self._praw_ok = False
            return self._fetch_via_json(subreddit, keyword)

        except prawcore.exceptions.Forbidden:
            logger.warning("r/%s is private/banned — skipping.", subreddit)

        except prawcore.exceptions.NotFound:
            logger.warning("r/%s does not exist — skipping.", subreddit)

        except prawcore.exceptions.ResponseException as exc:
            logger.error("PRAW ResponseException on r/%s: %s", subreddit, exc)
            self._praw_ok = False
            return self._fetch_via_json(subreddit, keyword)

        except Exception as exc:
            logger.error("PRAW unexpected error on r/%s: %s", subreddit, exc)

        return results

    def _fetch_via_json(self, subreddit: str, keyword: str) -> list[dict]:
        """
        Unauthenticated .json endpoint fallback.
        URL: https://www.reddit.com/r/{sub}/search.json?q=...&sort=new&restrict_sr=1&limit=25
        Reddit allows ~10 req/min unauthenticated — we stay well under that.
        """
        url = (
            f"https://www.reddit.com/r/{subreddit}/search.json"
            f"?q={requests.utils.quote(keyword)}"
            f"&sort=new&restrict_sr=1&t=week&limit={POSTS_PER_SEARCH}"
        )
        headers = {"User-Agent": _JSON_UA}

        try:
            resp = requests.get(url, headers=headers, timeout=10)

            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", DEFAULT_BACKOFF))
                logger.warning(
                    ".json 429 on r/%s — backing off %ds.", subreddit, wait
                )
                time.sleep(wait)
                return []   # skip this sub/keyword this cycle

            if resp.status_code == 403:
                logger.warning("r/%s is private (403 on .json) — skipping.", subreddit)
                return []

            if resp.status_code == 404:
                logger.warning("r/%s not found (404 on .json) — skipping.", subreddit)
                return []

            resp.raise_for_status()
            data = resp.json()

        except requests.exceptions.Timeout:
            logger.warning(".json timeout on r/%s + %r — skipping.", subreddit, keyword)
            return []
        except Exception as exc:
            logger.error(".json fetch error on r/%s: %s", subreddit, exc)
            return []

        children = data.get("data", {}).get("children", [])
        results = []
        for child in children:
            d = child.get("data", {})
            if not d:
                continue
            results.append({
                "id":           d.get("id", ""),
                "title":        d.get("title", ""),
                "selftext":     d.get("selftext", ""),
                "url":          f"https://www.reddit.com{d.get('permalink', '')}",
                "author":       d.get("author"),
                "score":        d.get("score", 0),
                "num_comments": d.get("num_comments", 0),
                "created_utc":  d.get("created_utc"),
                "subreddit":    d.get("subreddit", subreddit),
            })
        return results

    # -----------------------------------------------------------------------
    # Normalization
    # -----------------------------------------------------------------------

    def _normalize_praw_post(self, submission) -> dict:
        """Convert a PRAW Submission object into our internal post dict."""
        return {
            "id":           submission.id,
            "title":        submission.title or "",
            "selftext":     submission.selftext or "",
            "url":          f"https://www.reddit.com{submission.permalink}",
            "author":       str(submission.author) if submission.author else None,
            "score":        submission.score,
            "num_comments": submission.num_comments,
            "created_utc":  submission.created_utc,
            "subreddit":    str(submission.subreddit),
        }

    def _build_raw_post(self, post: dict, subreddit: str) -> dict:
        """
        Convert a normalized post dict → RawPost via make_raw_post().
        NEVER construct the RawPost dict manually — always use the helper.
        """
        title    = post.get("title", "").strip()
        selftext = post.get("selftext", "").strip()

        # Combine title + body as specified in the contract
        text = f"{title}\n{selftext}".strip() if selftext else title

        # Timestamp: prefer created_utc (unix) → fallback to now
        ts = self._unix_to_iso(post.get("created_utc"))

        sub_name = post.get("subreddit") or subreddit

        return make_raw_post(
            source      = f"reddit/r/{sub_name}",
            source_type = "reddit",
            text        = text,
            url         = post.get("url", ""),
            author      = post.get("author"),
            timestamp   = ts,
            metadata    = {
                "subreddit":    sub_name,
                "score":        post.get("score", 0),
                "num_comments": post.get("num_comments", 0),
                "geo_proxy":    GEO_MAP.get(sub_name.lower()),   # None if not mapped
            },
        )

    # -----------------------------------------------------------------------
    # Deduplication — two layers
    # -----------------------------------------------------------------------

    def _is_seen(self, post_id: str) -> bool:
        """Check in-memory set first (fast), then SQLite (persistent)."""
        if post_id in self._seen_ids:
            return True
        if self._store is not None:
            try:
                return self._store.is_post_seen(post_id, source="reddit")
            except Exception:
                pass    # SQLite failure → treat as not seen (safe: may re-enqueue once)
        return False

    def _mark_seen(self, post_id: str) -> None:
        """Add to in-memory set and persist to SQLite."""
        # Cap in-memory set to prevent unbounded growth over long runs
        if len(self._seen_ids) >= SEEN_IDS_CAP:
            logger.info(
                "RedditCrawler: _seen_ids hit cap (%d) — clearing.", SEEN_IDS_CAP
            )
            self._seen_ids.clear()

        self._seen_ids.add(post_id)

        if self._store is not None:
            try:
                self._store.mark_post_seen(post_id, source="reddit")
            except Exception as exc:
                logger.warning("Could not persist seen ID %s: %s", post_id, exc)

    # -----------------------------------------------------------------------
    # Utilities
    # -----------------------------------------------------------------------

    @staticmethod
    def _unix_to_iso(created_utc) -> str:
        """Convert Reddit's unix timestamp → ISO8601 string."""
        if created_utc is None:
            return datetime.now(timezone.utc).isoformat()
        try:
            return datetime.fromtimestamp(float(created_utc), tz=timezone.utc).isoformat()
        except (ValueError, OSError, OverflowError):
            return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _parse_retry_after(exc) -> int | None:
        """Extract Retry-After seconds from a prawcore TooManyRequests exception."""
        try:
            # prawcore stores the response on the exception
            return int(exc.response.headers.get("Retry-After", DEFAULT_BACKOFF))
        except Exception:
            return None