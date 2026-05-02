"""
analysis/trend_analyzer.py - Trend Analysis Engine | OWNER: Engineer B
Computes signal volume over time, integrates Google Trends correlation.
"""
from datetime import datetime, timedelta
from pytrends.request import TrendReq
from storage.sqlite_store import get_genomes_by_period


class TrendAnalyzer:
    def __init__(self):
        self.pytrends = TrendReq(hl="en-US", tz=360)

    def signal_trend(self, drug: str, days: int = 30) -> dict:
        """Returns daily signal counts for a drug over N days."""
        since  = datetime.utcnow() - timedelta(days=days)
        genomes = get_genomes_by_period(drug=drug, since=since)

        # Group by date
        by_date = {}
        for g in genomes:
            date = g["created_at"][:10]
            by_date[date] = by_date.get(date, 0) + 1

        return {"drug": drug, "days": days, "timeline": by_date}

    def google_trends_correlation(self, keywords: list, timeframe: str = "today 30-d") -> dict:
        """
        Fetch Google Trends data for keywords.
        Returns interest_over_time and interest_by_region dicts.
        """
        try:
            self.pytrends.build_payload(keywords[:5], timeframe=timeframe)
            return {
                "interest_over_time": self.pytrends.interest_over_time().to_dict(),
                "interest_by_region": self.pytrends.interest_by_region(
                    resolution="COUNTRY").to_dict(),
                "related_queries":    self.pytrends.related_queries(),
            }
        except Exception as e:
            return {"error": str(e)}

    def top_entities(self, project_id: str, days: int = 7) -> dict:
        """Returns top drugs, symptoms, signal types for a project."""
        since   = datetime.utcnow() - timedelta(days=days)
        genomes = get_genomes_by_period(project_id=project_id, since=since)

        drugs, symptoms, types = {}, {}, {}
        for g in genomes:
            for d in g.get("drugs", []):
                drugs[d] = drugs.get(d, 0) + 1
            for s in g.get("symptoms", []):
                symptoms[s] = symptoms.get(s, 0) + 1
            t = g.get("signal_type", "general")
            types[t] = types.get(t, 0) + 1

        return {
            "top_drugs":    sorted(drugs.items(),    key=lambda x: -x[1])[:10],
            "top_symptoms": sorted(symptoms.items(), key=lambda x: -x[1])[:10],
            "signal_types": types,
        }
