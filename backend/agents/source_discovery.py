"""
source_discovery.py — SourceDiscoveryAgent (Agentic Bonus)

An autonomous agent that:
  1. Watches for high-novelty genomes (score > 0.7)
  2. Identifies what SOURCE the signal came from
  3. Discovers NEW related sources not yet in Engineer A's crawler list
     by querying Reddit search, Google (via pytrends related queries),
     and known health forum patterns
  4. Emits DiscoveredSource objects for Engineer A to add to crawlers

This is the "agentic" layer — it runs on a schedule (every 30 min)
and makes decisions about what to monitor next.

Agentic loop:
  observe → reason → act → report

observe: pull high-novelty genomes from ChromaDB
reason:  find source patterns (which subreddits, forums, sites?)
act:     search for related communities not yet monitored  
report:  return DiscoveredSource list to Engineer A's source registry
"""

import re
import logging
import requests
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Known source registry — we already crawl these
# ---------------------------------------------------------------------------

KNOWN_REDDIT_SUBS = {
    "r/diabetes", "r/diabetes_t2", "r/loseit", "r/weightloss",
    "r/ozempic", "r/semaglutide", "r/tirzepatide",
    "r/askdocs", "r/medicine", "r/pharmacy", "r/nursing",
    "r/chronicpain", "r/ibs", "r/crohnsdisease",
    "r/mentalhealth", "r/depression", "r/anxiety",
    "r/parenting", "r/beyondthebump", "r/breastfeeding",
}

KNOWN_FORUMS = {
    "patient.info", "healthunlocked.com", "patientslikeme.com",
    "drugs.com/comments", "webmd.com/drugs", "medschat.com",
    "askapatient.com", "everydayhealth.com", "healingwell.com",
}

# URL patterns for health forums we can discover
FORUM_PATTERNS = [
    re.compile(r"forum\.", re.I),
    re.compile(r"community\.", re.I),
    re.compile(r"patient[s]?\.", re.I),
    re.compile(r"/forum[s]?/", re.I),
    re.compile(r"/discuss", re.I),
    re.compile(r"support[\.-]group", re.I),
]


# ---------------------------------------------------------------------------
# Discovered source dataclass
# ---------------------------------------------------------------------------

@dataclass
class DiscoveredSource:
    source_id:    str
    source_type:  str          # reddit | forum | rss | twitter
    url:          str
    name:         str          # human-readable
    drug_context: str          # what drug triggered discovery
    signal_type:  str          # what signal we expect here
    confidence:   float        # how confident we are this is useful (0-1)
    discovered_at: str
    reason:       str          # why the agent chose this source
    already_known: bool = False


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class SourceDiscoveryAgent:
    """
    Agentic source discovery. 

    Observe → Reason → Act loop:
      .run_cycle() — main entry point, called on a schedule
      .discover_for_drug(drug) — targeted discovery for a specific drug
    """

    REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"
    REDDIT_SUB_SEARCH = "https://www.reddit.com/subreddits/search.json"

    def __init__(self):
        from storage.chroma_store import get_chroma_store
        self._store = get_chroma_store()
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "PatientSafetySentinel/1.0 (research; safety monitoring)"
        })

    # ------------------------------------------------------------------
    # Main agentic loop
    # ------------------------------------------------------------------

    def run_cycle(self) -> list[DiscoveredSource]:
        """
        Full observe→reason→act cycle.
        Returns list of newly discovered sources.
        """
        logger.info("SourceDiscoveryAgent: starting cycle...")

        # OBSERVE — find high-novelty genomes from last 24h
        high_novelty_genomes = self._observe_high_novelty()

        if not high_novelty_genomes:
            logger.info("No high-novelty genomes to act on.")
            return []

        # REASON — extract unique drug+source patterns
        drug_source_map = self._reason_about_sources(high_novelty_genomes)

        # ACT — discover new sources for each drug
        discovered = []
        for drug, existing_sources in drug_source_map.items():
            new_sources = self._act_discover(drug, existing_sources)
            discovered.extend(new_sources)

        # Deduplicate by URL
        seen_urls = set()
        unique    = []
        for src in discovered:
            if src.url not in seen_urls:
                seen_urls.add(src.url)
                unique.append(src)

        logger.info(
            f"SourceDiscoveryAgent: cycle complete. "
            f"Discovered {len(unique)} new sources."
        )
        return unique

    def discover_for_drug(self, drug: str) -> list[DiscoveredSource]:
        """Targeted discovery for a single drug. Used when outbreak fires."""
        return self._act_discover(drug, existing_sources=set())

    def discover(self, topic: str, keywords: list[str]) -> list[dict]:
        """Discover candidate sources from a topic and optional keyword list."""
        search_terms = [topic.strip()] + [kw.strip() for kw in keywords if kw.strip()]
        seen_ids = set()
        discovered = []

        for term in search_terms[:4]:
            if not term:
                continue
            discovered.extend(self._discover_reddit_subs(term))
            discovered.extend(self._discover_forums(term))
            discovered.extend(self._discover_fda_feeds(term))

        unique = []
        for src in discovered:
            if src.source_id in seen_ids:
                continue
            seen_ids.add(src.source_id)
            unique.append(asdict(src))

        return unique

    # ------------------------------------------------------------------
    # OBSERVE — pull high-novelty genomes
    # ------------------------------------------------------------------

    def _observe_high_novelty(self) -> list[dict]:
        """Query ChromaDB for recently stored high-novelty genomes."""
        try:
            # Use a broad similarity query — find anything recent with high novelty
            # ChromaDB doesn't support "novelty_score > 0.7" directly in where clause
            # with float comparison in all versions, so we fetch recent and filter
            results = self._store._get_collection().get(
                where={"novelty_score": {"$gte": 0.7}},
                include=["metadatas"],
                limit=50,
            )
            return results.get("metadatas", [])
        except Exception as e:
            logger.warning(f"Could not fetch high-novelty genomes: {e}")
            return []

    # ------------------------------------------------------------------
    # REASON — what drugs/sources are we seeing?
    # ------------------------------------------------------------------

    def _reason_about_sources(
        self, genomes: list[dict]
    ) -> dict[str, set]:
        """
        Extract drug → {existing source_types} mapping from genomes.
        Helps us decide WHERE to look for new sources.
        """
        drug_sources: dict[str, set] = {}

        for g in genomes:
            drug        = g.get("drug", "").lower()
            source_type = g.get("source_type", "")
            if drug:
                drug_sources.setdefault(drug, set()).add(source_type)

        logger.info(
            f"REASON: {len(drug_sources)} drugs with high novelty signals: "
            f"{list(drug_sources.keys())[:5]}"
        )
        return drug_sources

    # ------------------------------------------------------------------
    # ACT — find new sources
    # ------------------------------------------------------------------

    def _act_discover(
        self,
        drug:             str,
        existing_sources: set,
    ) -> list[DiscoveredSource]:
        """
        Multi-strategy source discovery for a drug.
        Returns list of DiscoveredSource objects.
        """
        discovered = []

        # Strategy 1 — Reddit subreddit search
        reddit_sources = self._discover_reddit_subs(drug)
        discovered.extend(reddit_sources)

        # Strategy 2 — Known health forum patterns
        forum_sources = self._discover_forums(drug)
        discovered.extend(forum_sources)

        # Strategy 3 — FDA MedWatch / RSS feeds
        fda_sources = self._discover_fda_feeds(drug)
        discovered.extend(fda_sources)

        return discovered

    def _discover_reddit_subs(self, drug: str) -> list[DiscoveredSource]:
        """Search Reddit for subreddits discussing this drug."""
        sources = []
        try:
            resp = self._session.get(
                self.REDDIT_SUB_SEARCH,
                params={"q": drug, "limit": 10, "type": "sr"},
                timeout=8,
            )
            if resp.status_code != 200:
                return []

            data      = resp.json()
            children  = data.get("data", {}).get("children", [])

            for child in children:
                sub_data = child.get("data", {})
                name     = sub_data.get("display_name_prefixed", "")  # "r/something"
                sub_name = sub_data.get("display_name", "")
                title    = sub_data.get("title", "")
                subs     = sub_data.get("subscribers", 0)
                url      = f"https://www.reddit.com/{name}"

                if not name:
                    continue

                # Skip if already known
                already_known = name.lower() in KNOWN_REDDIT_SUBS

                # Score relevance
                relevance = self._score_reddit_relevance(
                    drug, sub_name, title, subs
                )
                if relevance < 0.4:
                    continue

                sources.append(DiscoveredSource(
                    source_id=f"reddit_{sub_name.lower()}",
                    source_type="reddit",
                    url=url,
                    name=name,
                    drug_context=drug,
                    signal_type="adverse_drug_reaction",
                    confidence=relevance,
                    discovered_at=datetime.now(timezone.utc).isoformat(),
                    reason=(
                        f"Subreddit '{name}' ({subs:,} subscribers) "
                        f"discusses {drug}. Title: '{title[:60]}'"
                    ),
                    already_known=already_known,
                ))

        except requests.RequestException as e:
            logger.debug(f"Reddit subreddit search failed for {drug}: {e}")

        return sources

    def _discover_forums(self, drug: str) -> list[DiscoveredSource]:
        """
        Check known health forum patterns for drug-specific pages.
        These are static rules — no scraping, just URL construction.
        """
        sources  = []
        drug_enc = requests.utils.quote(drug)

        candidate_urls = [
            (
                f"https://www.drugs.com/comments/{drug_enc}.html",
                f"Drugs.com user reviews for {drug}",
                "forum",
                0.85,
                "High-traffic drug review site with structured ADR reports",
            ),
            (
                f"https://www.askapatient.com/viewrating.asp?drug={drug_enc}",
                f"AskAPatient reviews for {drug}",
                "forum",
                0.80,
                "Patient review site focused on side effects",
            ),
            (
                f"https://www.rxisk.org/search/?q={drug_enc}",
                f"RxISK adverse effect reports for {drug}",
                "forum",
                0.90,
                "Independent ADR reporting site — high signal quality",
            ),
            (
                f"https://healthunlocked.com/search/{drug_enc}",
                f"HealthUnlocked community posts about {drug}",
                "forum",
                0.75,
                "NHS-linked patient community with condition-specific groups",
            ),
            (
                f"https://www.patientlikeme.com/search?q={drug_enc}",
                f"PatientsLikeMe data for {drug}",
                "forum",
                0.80,
                "Structured patient outcome data — good for ADR frequency",
            ),
        ]

        for url, name, source_type, confidence, reason in candidate_urls:
            domain = url.split("/")[2]
            already = domain in KNOWN_FORUMS

            sources.append(DiscoveredSource(
                source_id=f"forum_{domain}_{drug.lower().replace(' ', '_')}",
                source_type=source_type,
                url=url,
                name=name,
                drug_context=drug,
                signal_type="adverse_drug_reaction",
                confidence=confidence,
                discovered_at=datetime.now(timezone.utc).isoformat(),
                reason=reason,
                already_known=already,
            ))

        return sources

    def _discover_fda_feeds(self, drug: str) -> list[DiscoveredSource]:
        """
        FDA MedWatch and openFDA RSS/API endpoints for this drug.
        Always high value — FDA is authoritative.
        """
        drug_enc = requests.utils.quote(drug)
        sources  = []

        fda_endpoints = [
            (
                f"https://api.fda.gov/drug/event.json?search=patient.drug.medicinalproduct:\"{drug}\"&limit=100",
                f"openFDA FAERS adverse events for {drug}",
                "rss",
                0.95,
                "Official FDA adverse event reporting system — ground truth",
            ),
            (
                f"https://www.fda.gov/safety/medwatch-fda-safety-information-and-adverse-event-reporting-program",
                "FDA MedWatch Safety Reports RSS",
                "rss",
                0.90,
                "FDA MedWatch — official drug safety communications",
            ),
        ]

        for url, name, source_type, confidence, reason in fda_endpoints:
            sources.append(DiscoveredSource(
                source_id=f"fda_{drug.lower().replace(' ', '_')}",
                source_type=source_type,
                url=url,
                name=name,
                drug_context=drug,
                signal_type="adverse_drug_reaction",
                confidence=confidence,
                discovered_at=datetime.now(timezone.utc).isoformat(),
                reason=reason,
                already_known=False,
            ))

        return sources

    # ------------------------------------------------------------------
    # Relevance scoring helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _score_reddit_relevance(
        drug: str, sub_name: str, title: str, subscribers: int
    ) -> float:
        """Score how relevant a subreddit is for a drug signal."""
        score = 0.0
        text  = f"{sub_name} {title}".lower()
        drug_lower = drug.lower()

        # Direct drug mention
        if drug_lower in text:
            score += 0.5

        # Health/medical context keywords
        health_kw = [
            "health", "medical", "medicine", "drug", "medication",
            "patient", "disease", "condition", "symptom", "side effect",
            "diabetes", "chronic", "treatment", "therapy", "pharma",
        ]
        score += sum(0.05 for kw in health_kw if kw in text)

        # Subscriber count — prefer active communities
        if subscribers > 100_000:
            score += 0.2
        elif subscribers > 10_000:
            score += 0.1
        elif subscribers > 1_000:
            score += 0.05

        return min(1.0, score)


# ---------------------------------------------------------------------------
# Module singleton
# ---------------------------------------------------------------------------

_agent_instance: Optional[SourceDiscoveryAgent] = None


def get_source_discovery_agent() -> SourceDiscoveryAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = SourceDiscoveryAgent()
    return _agent_instance