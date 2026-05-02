"""
agents/source_discovery.py - Source Discovery Agent | OWNER: Engineer B
AGENTIC BONUS: Given a topic/drug, automatically discovers relevant 
online communities and scores them for relevance and credibility.
"""
import requests
from dataclasses import dataclass, asdict

REDDIT_SUBREDDIT_SEARCH = "https://www.reddit.com/subreddits/search.json"

GEO_SUBREDDITS = {
    "IN": ["india", "Kerala", "mumbai", "Chennai", "delhi"],
    "US": ["unitedstates", "AskAmericans"],
    "GB": ["unitedkingdom"],
}

LOW_CREDIBILITY = ["conspiracy", "conspiracy_commons", "quackery", "alternativemedicine"]

RSS_HEALTH_SOURCES = [
    {"name": "FDA MedWatch",  "url": "https://www.fda.gov/about-fda/contact-fda/stay-informed/rss-feeds/medwatch-safety-alerts/rss.xml", "credibility": 1.0},
    {"name": "WHO News",      "url": "https://www.who.int/rss-feeds/news-english.xml",  "credibility": 1.0},
    {"name": "Reuters Health","url": "https://feeds.reuters.com/reuters/healthNews",     "credibility": 0.9},
]


@dataclass
class DiscoveredSource:
    name: str
    url: str
    source_type: str          # reddit | forum | rss
    relevance_score: float
    credibility_score: float
    member_count: int = 0
    posts_per_day: float = 0.0
    flagged_low_credibility: bool = False
    recommended: bool = True

    def to_dict(self):
        return asdict(self)


class SourceDiscoveryAgent:
    """
    Agentic source discovery:
    1. Searches Reddit for relevant subreddits
    2. Scores each by relevance + credibility
    3. Returns ranked list for human approval
    """

    def discover(self, topic: str, keywords: list) -> list:
        """
        Main entry point.
        Returns list of DiscoveredSource sorted by relevance_score desc.
        """
        discovered = []
        discovered.extend(self._search_reddit(topic, keywords))
        discovered.extend(self._get_rss_sources(keywords))
        discovered.sort(key=lambda s: s.relevance_score, reverse=True)
        return [s.to_dict() for s in discovered]

    def _search_reddit(self, topic: str, keywords: list) -> list:
        results = []
        try:
            resp = requests.get(
                REDDIT_SUBREDDIT_SEARCH,
                params={"q": topic, "limit": 20},
                headers={"User-Agent": "PatientSafetySentinel/1.0"},
                timeout=10)
            subs = resp.json().get("data", {}).get("children", [])

            for sub in subs:
                data = sub.get("data", {})
                name = data.get("display_name", "")
                desc = (data.get("public_description", "") + " " +
                        data.get("title", "")).lower()
                members = data.get("subscribers", 0)

                low_cred = name.lower() in LOW_CREDIBILITY
                relevance = self._score_relevance(desc, keywords)
                credibility = 0.2 if low_cred else min(1.0, members / 500000)

                results.append(DiscoveredSource(
                    name=f"r/{name}",
                    url=f"https://reddit.com/r/{name}",
                    source_type="reddit",
                    relevance_score=relevance,
                    credibility_score=credibility,
                    member_count=members,
                    flagged_low_credibility=low_cred,
                    recommended=relevance > 0.4 and not low_cred,
                ))
        except Exception as e:
            print(f"Reddit discovery error: {e}")
        return results

    def _get_rss_sources(self, keywords: list) -> list:
        return [
            DiscoveredSource(
                name=src["name"], url=src["url"],
                source_type="rss",
                relevance_score=self._score_relevance(src["name"], keywords),
                credibility_score=src["credibility"],
                recommended=True,
            )
            for src in RSS_HEALTH_SOURCES
        ]

    def _score_relevance(self, text: str, keywords: list) -> float:
        """Simple keyword overlap relevance score 0.0 to 1.0."""
        if not text or not keywords:
            return 0.0
        hits = sum(1 for kw in keywords if kw.lower() in text.lower())
        return min(1.0, hits / max(len(keywords), 1))
