"""
routes/signals.py - Signal genome API | OWNER: Engineer C
Read genomes, filter by project/drug/type/date.
"""
from fastapi import APIRouter, Query
from storage.sqlite_store import get_conn
import json

router = APIRouter()


@router.get("/")
def list_signals(
    project_id: str = Query(None),
    signal_type: str = Query(None),
    drug: str = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    query  = "SELECT * FROM genomes WHERE 1=1"
    params = []
    if project_id:
        query += " AND project_id=?"; params.append(project_id)
    if signal_type:
        query += " AND signal_type=?"; params.append(signal_type)
    if drug:
        query += " AND drugs LIKE ?"; params.append(f"%{drug}%")
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


@router.get("/{genome_id}")
def get_signal(genome_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM genomes WHERE genome_id=?", (genome_id,)).fetchone()
        return dict(row) if row else {}
