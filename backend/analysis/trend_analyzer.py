"""
trend_analyzer.py — Google Trends + internal signal trend analysis

Two jobs:
  1. External trends  — pytrends Google Trends API for a drug/symptom pair
                        Enriches genome.geo.google_trends_region
  2. Internal trends  — queries ChromaDB to see if a signal is growing
                        over time (used by Engineer C's dashboard endpoint)

pytrends is rate-limited. We cache results for 1 hour per query.
All network calls have timeouts and fail gracefully.
"""

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy pytrends loader
# ---------------------------------------------------------------------------

_pytrends = None


def _get_pytrends():
    global _pytrends
    if _pytrends is None:
        try:
            from pytrends.request import TrendReq
            _pytrends = TrendReq(
                hl="en-US",
                tz=0,           # UTC
                timeout=(5, 15),  # (connect, read)
                retries=1,
                backoff_factor=0.5,
            )
            logger.info("pytrends client initialised.")
        except ImportError:
            logger.warning("pytrends not installed — Google Trends disabled.")
            _pytrends = None
    return _pytrends


# ---------------------------------------------------------------------------
# In-process cache (TTL = 1 hour — pytrends rate limits aggressively)
# ---------------------------------------------------------------------------

_trends_cache: dict[str, tuple[dict, float]] = {}   # key → (result, timestamp)
CACHE_TTL_SECONDS = 3600


def _cache_get(key: str) -> Optional[dict]:
    if key in _trends_cache:
        result, ts = _trends_cache[key]
        if time.time() - ts < CACHE_TTL_SECONDS:
            return result
        del _trends_cache[key]
    return None


def _cache_set(key: str, value: dict):
    _trends_cache[key] = (value, time.time())


# ---------------------------------------------------------------------------
# TrendAnalyzer
# ---------------------------------------------------------------------------

class TrendAnalyzer:
    """
    Call .get_trends(drug, symptom) → TrendResult dict
    Call .get_internal_trend(drug, symptom) → list of counts by hour
    """

    def get_trends(self, drug: str, symptom: str) -> dict:
        """
        Fetch Google Trends interest for drug+symptom.
        Returns a dict suitable for enriching genome.geo fields.

        Returns:
            {
                "google_trends_region": str,   # top region/country
                "trend_score": float,           # 0-100 normalised
                "rising": bool,                 # is it trending up?
                "related_queries": list[str],
                "source": "google_trends" | "unavailable"
            }
        """
        cache_key = f"trends:{drug.lower()}:{symptom.lower()}"
        cached = _cache_get(cache_key)
        if cached:
            return cached

        pt = _get_pytrends()
        if pt is None:
            return self._unavailable_result()

        try:
            keywords = [f"{drug} {symptom}"][:5]  # pytrends max 5 kw

            pt.build_payload(
                kw_list=keywords,
                cat=0,          # all categories
                timeframe="now 7-d",
                geo="",         # worldwide
            )

            # Interest by region
            by_region = pt.interest_by_region(resolution="COUNTRY", inc_low_vol=False)

            top_region = ""
            trend_score = 0.0

            if not by_region.empty:
                # Top country by interest
                col = keywords[0]
                if col in by_region.columns:
                    top_row    = by_region[col].idxmax()
                    trend_score = float(by_region[col].max())
                    top_region  = str(top_row)

            # Related rising queries
            related = pt.related_queries()
            rising_queries = []
            for kw, data in related.items():
                if data and data.get("rising") is not None:
                    rq = data["rising"]
                    if rq is not None and not rq.empty:
                        rising_queries = rq["query"].tolist()[:5]
                        break

            # Is it trending up? Check over time
            over_time = pt.interest_over_time()
            is_rising = False
            if not over_time.empty and keywords[0] in over_time.columns:
                series   = over_time[keywords[0]].tolist()
                if len(series) >= 4:
                    # Rising if last quarter is higher than first quarter
                    mid      = len(series) // 2
                    is_rising = (sum(series[mid:]) / len(series[mid:])
                                 > sum(series[:mid]) / len(series[:mid]))

            result = {
                "google_trends_region": top_region,
                "trend_score":          round(trend_score, 2),
                "rising":               is_rising,
                "related_queries":      rising_queries,
                "source":               "google_trends",
            }

            _cache_set(cache_key, result)
            logger.info(
                f"Google Trends: {drug}+{symptom} → region={top_region}, "
                f"score={trend_score:.1f}, rising={is_rising}"
            )
            return result

        except Exception as e:
            logger.warning(f"pytrends failed for {drug}/{symptom}: {e}")
            return self._unavailable_result()

    def get_internal_trend(
        self,
        drug:    str,
        symptom: str,
        hours:   int = 24,
    ) -> list[dict]:
        """
        Query ChromaDB for hourly signal counts over the last N hours.
        Returns list of {"hour": ISO string, "count": int} dicts.
        Used by Engineer C's /trends endpoint for the dashboard chart.
        """
        from storage.chroma_store import get_chroma_store
        store = get_chroma_store()

        now     = datetime.now(timezone.utc)
        buckets = []

        for h in range(hours, 0, -1):
            window_end   = now - timedelta(hours=h - 1)
            window_start = now - timedelta(hours=h)

            # query_by_drug_symptom uses a single window — approximate with
            # counting and differencing
            recent = store.query_by_drug_symptom(drug, symptom, hours=h)

            # Count only those in this specific 1-hour bucket
            bucket_count = sum(
                1 for g in recent
                if window_start.isoformat() <= g.get("created_at", "") < window_end.isoformat()
            )

            buckets.append({
                "hour":  window_start.isoformat(),
                "count": bucket_count,
            })

        return buckets

    def enrich_genome_geo(self, genome: dict, drug: str, symptom: str) -> dict:
        """
        Convenience method called by PipelineProcessor (optional enrichment).
        Updates genome.geo.google_trends_region in place.
        Non-blocking: failures silently leave field empty.
        """
        try:
            trends = self.get_trends(drug, symptom)
            genome["geo"]["google_trends_region"] = trends.get("google_trends_region", "")
            genome["geo"]["confidence"] = min(
                1.0,
                genome["geo"].get("confidence", 0.5)
                + (0.2 if trends["source"] == "google_trends" else 0.0)
            )
        except Exception as e:
            logger.debug(f"Trend geo enrichment failed (non-fatal): {e}")
        return genome

    def signal_trend(self, drug: str, days: int = 30) -> dict:
        """
        Get signal count timeline for a drug over the last N days.
        Returns {"timeline": {"2024-01-01": 5, "2024-01-02": 3, ...}}
        Used by the frontend trends panel.
        """
        from storage.sqlite_store import get_conn
        from datetime import datetime, timedelta

        timeline = {}
        now = datetime.now()

        # Generate timeline for last N days
        for i in range(days):
            date = (now - timedelta(days=i)).strftime('%Y-%m-%d')
            timeline[date] = 0

        try:
            with get_conn() as conn:
                # Query genomes table for signals containing this drug in the drugs column
                rows = conn.execute("""
                    SELECT DATE(created_at) as date, COUNT(*) as count
                    FROM genomes
                    WHERE drugs LIKE ?
                    AND created_at >= ?
                    GROUP BY DATE(created_at)
                """, (f'%{drug}%', (now - timedelta(days=days)).isoformat()))

                # Update timeline with actual counts
                for row in rows:
                    date_str = row['date']
                    if date_str in timeline:
                        timeline[date_str] = row['count']

        except Exception as e:
            logger.warning(f"Failed to get signal trend for {drug}: {e}")

        return {"timeline": timeline}

    @staticmethod
    def _unavailable_result() -> dict:
        return {
            "google_trends_region": "",
            "trend_score":          0.0,
            "rising":               False,
            "related_queries":      [],
            "source":               "unavailable",
        }


# ---------------------------------------------------------------------------
# Module singleton
# ---------------------------------------------------------------------------

_analyzer_instance: Optional[TrendAnalyzer] = None


def get_trend_analyzer() -> TrendAnalyzer:
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = TrendAnalyzer()
    return _analyzer_instance