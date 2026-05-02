"""
routes/alerts.py - Alerts and outbreaks API | OWNER: Engineer C
"""
from fastapi import APIRouter, Query
from storage.sqlite_store import get_conn

router = APIRouter()


@router.get("/")
def list_alerts(resolved: bool = Query(False), limit: int = 50):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM alerts WHERE resolved=? ORDER BY created_at DESC LIMIT ?",
            (int(resolved), limit)).fetchall()
        return [dict(r) for r in rows]


@router.get("/outbreaks")
def list_outbreaks(limit: int = 20):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM outbreaks ORDER BY created_at DESC LIMIT ?",
            (limit,)).fetchall()
        return [dict(r) for r in rows]


@router.patch("/{alert_id}/resolve")
def resolve_alert(alert_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE alerts SET resolved=1 WHERE id=?", (alert_id,))
    return {"status": "resolved"}
