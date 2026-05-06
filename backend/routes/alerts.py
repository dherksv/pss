"""
routes/alerts.py | OWNER: Engineer C
"""
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
from storage.sqlite_store import get_conn
from datetime import datetime
import json

router = APIRouter()


def _parse_outbreak(row: dict) -> dict:
    for field in ["genome_ids", "regions"]:
        if isinstance(row.get(field), str):
            try: row[field] = json.loads(row[field])
            except: row[field] = []
    return row


# ── Alerts ────────────────────────────────────────────────────────────────────
@router.get("/")
def list_alerts(resolved: bool = Query(False), limit: int = Query(50, le=200)):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM alerts WHERE resolved=? ORDER BY created_at DESC LIMIT ?",
            (int(resolved), limit)
        ).fetchall()
        return [dict(r) for r in rows]


@router.post("/")
def create_alert(
    alert_type:  str,
    message:     str,
    genome_id:   Optional[str] = None,
    outbreak_id: Optional[str] = None,
):
    """Called internally by analysis engine when a signal is critical."""
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO alerts (genome_id, outbreak_id, alert_type, message, resolved, created_at)"
            " VALUES (?,?,?,?,0,?)",
            (genome_id, outbreak_id, alert_type, message, datetime.utcnow().isoformat())
        )
    return {"status": "created"}


@router.patch("/{alert_id}/resolve")
def resolve_alert(alert_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM alerts WHERE id=?", (alert_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Alert not found")
        conn.execute("UPDATE alerts SET resolved=1 WHERE id=?", (alert_id,))
    return {"status": "resolved", "alert_id": alert_id}


# ── Outbreaks ─────────────────────────────────────────────────────────────────
@router.get("/outbreaks")
def list_outbreaks(severity: str = Query(None), limit: int = Query(20, le=100)):
    query  = "SELECT * FROM outbreaks WHERE 1=1"
    params: list = []
    if severity:
        query += " AND severity=?"; params.append(severity)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [_parse_outbreak(dict(r)) for r in rows]


@router.get("/outbreaks/{outbreak_id}")
def get_outbreak(outbreak_id: str):
    """Single outbreak — used by OutbreakPanel detail view."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM outbreaks WHERE outbreak_id=?", (outbreak_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Outbreak not found")
        return _parse_outbreak(dict(row))