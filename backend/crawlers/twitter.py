"""
backend/crawlers/twitter.py

Twitter/X crawler for Patient Safety Sentinel.
Uses twitterapi.io — hackathon-provided endpoint with limited credits.

Credit conservation strategy (STRICT — do not relax):
    - Batch ALL keywords into ONE query per project using OR operator
    - Max 5 keywords per query (twitterapi.io limit)
    - Max 20 results per call (per spec)
    - Filter: lang:en -is:retweet (cuts noise, saves credits)
    - Deduplicate aggressively — never re-fetch a seen tweet ID
    - Rate-limit: enforce minimum 5-minute gap between calls per project
      (APScheduler already fires every 5min for realtime — this is a
       safety net against accidental double-fires)
"""

import logging
import queue
import time
from datetime import datetime, timezone

import requests

from .base import BaseCrawler, make_raw_post

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# twitterapi.io endpoint (hackathon-provided)
# ---------------------------------------------------------------------------
TWITTER_API_URL = "https://api.twitterapi.io/twitter/tweet/advanced_search"

# Hard limits — do not increase without checking credit balance
MAX_KEYWORDS_PER_QUERY = 5
MAX_RESULTS_PER_CALL   = 20

# Minimum seconds between calls per crawler instance (safety net)
MIN_CALL_INTERVAL = 290   # just under 5 minutes

# In-memory dedup cap
SEEN_IDS_CAP = 10_000


class TwitterCrawler(BaseCrawler):
    """
    Crawls Twitter/X for healthcare safety signals via twitterapi.io.

    Config keys expected in source_config:
        api_key   (str) — from TWITTER_API_KEY env var

    Optional:
        sqlite_store — passed for interface consistency with RedditCrawler,
                       used for persistent dedup if provided
    """

    def __init__(
        self,
        source_config: dict,
        keywords: list,
        post_queue: queue.Queue,
        sqlite_store=None,
    ):
        super().__init__(source_config, keywords, post_queue)

        self._api_key    = source_config.get("api_key", "")
        self._store      = sqlite_store
        self._seen_ids: set[str] = set()
        self._last_call: float   = 0.0   # unix timestamp of last API call

        if not self._api_key:
            logger.warning(
                "TwitterCrawler: TWITTER_API_KEY not set — "
                "all crawl() calls will no-op."
            )

        # Load persisted seen IDs from SQLite
        if self._store is not None:
            try:
                persisted = self._store.get_seen_post_ids(source="twitter")
                self._seen_ids.update(persisted)
                logger.info(
                    "Loaded %d persisted Twitter tweet IDs from SQLite cache.",
                    len(persisted),
                )
            except Exception as exc:
                logger.warning("Could not load persisted Twitter IDs: %s", exc)

    # -----------------------------------------------------------------------
    # Public API — called by APScheduler
    # -----------------------------------------------------------------------

    def crawl(self) -> None:
        """
        Main crawl entry point.
        Builds one batched query from all keywords, fires one API call,
        deduplicates results, and enqueues new posts as RawPost dicts.
        """
        if not self._api_key:
            logger.warning("TwitterCrawler: no API key — skipping crawl.")
            return

        # --- Safety net: enforce minimum interval between calls ---
        elapsed = time.time() - self._last_call
        if elapsed < MIN_CALL_INTERVAL and self._last_call > 0:
            wait = MIN_CALL_INTERVAL - elapsed
            logger.info(
                "TwitterCrawler: %.0fs since last call — "
                "waiting %.0fs to conserve credits.", elapsed, wait,
            )
            time.sleep(wait)

        query = self._build_query()
        logger.info("TwitterCrawler: querying — %r", query)

        tweets = self._fetch(query)
        self._last_call = time.time()

        if not tweets:
            logger.info("TwitterCrawler: no results returned.")
            return

        enqueued = 0
        for tweet in tweets:
            tweet_id = tweet.get("id")
            if not tweet_id:
                continue

            if self._is_seen(tweet_id):
                continue
            self._mark_seen(tweet_id)

            raw = self._build_raw_post(tweet)
            self._enqueue(raw)
            enqueued += 1

        logger.info(
            "TwitterCrawler: %d new tweet(s) enqueued (of %d returned).",
            enqueued, len(tweets),
        )

    # -----------------------------------------------------------------------
    # Query builder
    # -----------------------------------------------------------------------

    def _build_query(self) -> str:
        """
        Batch keywords into a single OR query — conserves API credits.

        Format:  "keyword1" OR "keyword2" OR ... lang:en -is:retweet

        Rules:
            - Max 5 keywords (twitterapi.io limit)
            - Each keyword quoted to match exact phrase
            - Append lang:en -is:retweet to cut noise
        """
        # Take first 5 keywords only
        kws = self.keywords[:MAX_KEYWORDS_PER_QUERY]
        query = " OR ".join(f'"{kw}"' for kw in kws)
        query += " lang:en -is:retweet"
        return query

    # -----------------------------------------------------------------------
    # API call
    # -----------------------------------------------------------------------

    def _fetch(self, query: str) -> list[dict]:
        """
        Call twitterapi.io advanced search endpoint.

        Returns a list of raw tweet dicts from the response.
        Never raises — all errors are caught and logged.

        Response shape from twitterapi.io:
            {
                "tweets": [
                    {
                        "id":           "...",
                        "text":         "...",
                        "createdAt":    "...",
                        "author":       {"userName": "..."},
                        "likeCount":    0,
                        "retweetCount": 0
                    }
                ]
            }
        """
        headers = {
            "X-API-Key":    self._api_key,
            "Content-Type": "application/json",
        }
        params = {
            "query":       query,
            "maxResults":  MAX_RESULTS_PER_CALL,
        }

        try:
            resp = requests.get(
                TWITTER_API_URL,
                headers=headers,
                params=params,
                timeout=15,
            )

            if resp.status_code == 401:
                logger.error(
                    "TwitterCrawler: 401 Unauthorized — check TWITTER_API_KEY."
                )
                return []

            if resp.status_code == 402:
                logger.error(
                    "TwitterCrawler: 402 Payment Required — "
                    "hackathon credits exhausted. All Twitter crawls suspended."
                )
                # Flip a flag so subsequent crawl() calls no-op immediately
                self._api_key = ""
                return []

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 60))
                logger.warning(
                    "TwitterCrawler: 429 rate limited — "
                    "backing off %ds.", retry_after,
                )
                time.sleep(retry_after)
                return []

            resp.raise_for_status()
            data = resp.json()

        except requests.exceptions.Timeout:
            logger.warning("TwitterCrawler: request timed out — skipping cycle.")
            return []
        except requests.exceptions.ConnectionError as exc:
            logger.error("TwitterCrawler: connection error — %s", exc)
            return []
        except Exception as exc:
            logger.error("TwitterCrawler: unexpected fetch error — %s", exc)
            return []

        tweets = data.get("tweets", [])
        if not isinstance(tweets, list):
            logger.warning(
                "TwitterCrawler: unexpected response shape — "
                "'tweets' is %s not list.", type(tweets).__name__,
            )
            return []

        return tweets

    # -----------------------------------------------------------------------
    # RawPost builder
    # -----------------------------------------------------------------------

    def _build_raw_post(self, tweet: dict) -> dict:
        """
        Convert a twitterapi.io tweet dict → RawPost via make_raw_post().
        NEVER construct the dict manually — always use the helper.
        """
        author_obj = tweet.get("author") or {}
        author     = author_obj.get("userName") or author_obj.get("name")

        tweet_id = tweet.get("id", "")
        url      = (
            f"https://twitter.com/i/web/status/{tweet_id}"
            if tweet_id else ""
        )

        ts = self._parse_timestamp(tweet.get("createdAt"))

        return make_raw_post(
            source      = "twitter",
            source_type = "twitter",
            text        = tweet.get("text", ""),
            url         = url,
            author      = author,
            timestamp   = ts,
            metadata    = {
                "likes":    tweet.get("likeCount", 0),
                "retweets": tweet.get("retweetCount", 0),
                "geo":      tweet.get("geo") or {},
            },
        )

    # -----------------------------------------------------------------------
    # Deduplication
    # -----------------------------------------------------------------------

    def _is_seen(self, tweet_id: str) -> bool:
        if tweet_id in self._seen_ids:
            return True
        if self._store is not None:
            try:
                return self._store.is_post_seen(tweet_id, source="twitter")
            except Exception:
                pass
        return False

    def _mark_seen(self, tweet_id: str) -> None:
        if len(self._seen_ids) >= SEEN_IDS_CAP:
            logger.info("TwitterCrawler: _seen_ids cap hit — clearing.")
            self._seen_ids.clear()
        self._seen_ids.add(tweet_id)
        if self._store is not None:
            try:
                self._store.mark_post_seen(tweet_id, source="twitter")
            except Exception as exc:
                logger.warning("Could not persist Twitter seen ID %s: %s", tweet_id, exc)

    # -----------------------------------------------------------------------
    # Utilities
    # -----------------------------------------------------------------------

    @staticmethod
    def _parse_timestamp(created_at: str | None) -> str:
        """
        Parse twitterapi.io's createdAt string → ISO8601.

        twitterapi.io returns timestamps in one of two formats:
            "Thu Apr 10 12:34:56 +0000 2025"   (Twitter legacy format)
            "2025-04-10T12:34:56.000Z"          (ISO format)
        """
        if not created_at:
            return datetime.now(timezone.utc).isoformat()

        # Try ISO format first
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                dt = datetime.strptime(created_at, fmt)
                return dt.replace(tzinfo=timezone.utc).isoformat()
            except ValueError:
                pass

        # Try Twitter legacy format
        try:
            dt = datetime.strptime(created_at, "%a %b %d %H:%M:%S +0000 %Y")
            return dt.replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            pass

        logger.warning("TwitterCrawler: could not parse timestamp %r — using now.", created_at)
        return datetime.now(timezone.utc).isoformat()