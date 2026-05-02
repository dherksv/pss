"""
routes/sources.py - Source discovery API | OWNER: Engineer C
Triggers Source Discovery Agent and returns discovered sources for approval.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from agents.source_discovery import SourceDiscoveryAgent

router = APIRouter()
agent  = SourceDiscoveryAgent()


class DiscoverRequest(BaseModel):
    topic: str
    keywords: list[str]


@router.post("/discover")
def discover_sources(req: DiscoverRequest):
    """
    Trigger the Source Discovery Agent.
    Returns ranked list of discovered sources for human approval.
    """
    sources = agent.discover(topic=req.topic, keywords=req.keywords)
    return {"discovered": sources, "count": len(sources)}
