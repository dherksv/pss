"""
routes/analysis.py | OWNER: Engineer C
"""
from fastapi import APIRouter, Query
from analysis.trend_analyzer import TrendAnalyzer

router   = APIRouter()
analyzer = TrendAnalyzer()


@router.get("/trends/{drug}")
def drug_trend(drug: str, days: int = Query(30, le=90)):
    return analyzer.signal_trend(drug=drug, days=days)


@router.get("/google-trends")
def google_trends(keywords: str = Query(...), timeframe: str = "today 30-d"):
    kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
    return analyzer.google_trends_correlation(kw_list, timeframe)


# Global top-entities (no project_id) — called by TrendPanel
@router.get("/top-entities")
def top_entities_global(days: int = Query(7, le=90)):
    return analyzer.top_entities(project_id=None, days=days)


# Per-project top-entities — called by ConfigPanel
@router.get("/top-entities/{project_id}")
def top_entities(project_id: str, days: int = Query(7, le=90)):
    return analyzer.top_entities(project_id=project_id, days=days)