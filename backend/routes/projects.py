"""
routes/projects.py - Project management CRUD | OWNER: Engineer C
Each project = one monitoring use case with keywords + sources + latency config.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uuid, json
from datetime import datetime
from storage.sqlite_store import get_conn

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────
class SourceConfig(BaseModel):
    type: str                    # reddit | twitter | forum | rss
    latency: str                 # realtime | daily | weekly
    subreddits: List[str] = []
    urls: List[str] = []
    feeds: List[str] = []
    selectors: dict = {}


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    keywords: List[str]
    sources: List[SourceConfig]


class ProjectUpdate(BaseModel):
    name:      Optional[str]       = None
    keywords:  Optional[List[str]] = None
    is_active: Optional[bool]      = None


# ── Routes ────────────────────────────────────────────────────────────────────
@router.get("/")
def list_projects():
    """List all monitoring projects."""
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["keywords"] = json.loads(d.get("keywords") or "[]")
            d["sources"]  = json.loads(d.get("sources")  or "[]")
            result.append(d)
        return result


@router.post("/", status_code=201)
def create_project(project: ProjectCreate):
    """Create a new monitoring project."""
    project_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO projects VALUES (?,?,?,?,?,?)",
            (
                project_id,
                project.name,
                json.dumps(project.keywords),
                json.dumps([s.dict() for s in project.sources]),
                datetime.utcnow().isoformat(),
                1,
            )
        )
    return {"project_id": project_id, "status": "created", "name": project.name}


@router.get("/{project_id}")
def get_project(project_id: str):
    """Get a single project by ID."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE id=?", (project_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")
        d = dict(row)
        d["keywords"] = json.loads(d.get("keywords") or "[]")
        d["sources"]  = json.loads(d.get("sources")  or "[]")
        return d

@router.patch("/{project_id}")
def update_project(project_id: str, update: ProjectUpdate):
    """Update project name, keywords, or active status."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM projects WHERE id=?", (project_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")
        if update.name is not None:
            conn.execute("UPDATE projects SET name=? WHERE id=?",
                         (update.name, project_id))
        if update.keywords is not None:
            conn.execute("UPDATE projects SET keywords=? WHERE id=?",
                         (json.dumps(update.keywords), project_id))
        if update.is_active is not None:
            conn.execute("UPDATE projects SET is_active=? WHERE id=?",
                         (int(update.is_active), project_id))
    return {"status": "updated", "project_id": project_id}        
