"""
routes/sources.py | OWNER: Engineer C
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from agents.source_discovery import SourceDiscoveryAgent

router = APIRouter()
agent  = SourceDiscoveryAgent()


class DiscoverRequest(BaseModel):
    topic: str
    keywords: List[str]


class ApproveRequest(BaseModel):
    project_id: str
    source_names: List[str]


@router.post("/discover")
def discover_sources(req: DiscoverRequest):
    """Trigger Source Discovery Agent — Config panel calls this."""
    discovered = agent.discover(topic=req.topic, keywords=req.keywords)
    return {"topic": req.topic, "keywords": req.keywords,
            "discovered": discovered, "count": len(discovered)}


@router.post("/approve")
def approve_sources(req: ApproveRequest):
    """Human approves selected sources from discovery results."""
    # TODO Engineer A: wire approved sources into scheduler for project
    return {
        "status":     "approved",
        "project_id": req.project_id,
        "approved":   req.source_names,
        "message":    f"{len(req.source_names)} sources added to project",
    }