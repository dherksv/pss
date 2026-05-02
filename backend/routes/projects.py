"""
routes/projects.py - Project management API | OWNER: Engineer C
CRUD for monitoring projects. Each project = one use case (eg: Ozempic monitoring)
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import uuid
from datetime import datetime
from storage.sqlite_store import get_conn

router = APIRouter()


class SourceConfig(BaseModel):
    type: str           # reddit | twitter | forum | rss
    latency: str        # realtime | daily | weekly
    subreddits: list = []
    urls: list = []
    feeds: list = []


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    keywords: list[str]
    sources: list[SourceConfig]


@router.get("/")
def list_projects():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM projects").fetchall()
        return [dict(r) for r in rows]


@router.post("/")
def create_project(project: ProjectCreate):
    import json
    project_id = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO projects VALUES (?,?,?,?,?,?)",
            (project_id, project.name,
             json.dumps(project.keywords),
             json.dumps([s.dict() for s in project.sources]),
             datetime.utcnow().isoformat(), 1)
        )
    return {"project_id": project_id, "status": "created"}


@router.get("/{project_id}")
def get_project(project_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Project not found")
        return dict(row)


@router.delete("/{project_id}")
def delete_project(project_id: str):
    with get_conn() as conn:
        conn.execute("UPDATE projects SET is_active=0 WHERE id=?", (project_id,))
    return {"status": "deactivated"}
