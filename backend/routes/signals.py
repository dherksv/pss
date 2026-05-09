"""
routes/signals.py | OWNER: Engineer C
"""
from fastapi import APIRouter, Query, HTTPException
from storage.sqlite_store import get_conn
import json

router = APIRouter()


def _parse(row: dict) -> dict:
    for field in ["drugs", "symptoms", "locations"]:
        if isinstance(row.get(field), str):
            try: row[field] = json.loads(row[field])
            except: row[field] = []

    # Reconstruct nested novelty metadata from normalized SQL columns.
    if "novelty_score" in row or "novelty_in_fda_label" in row or "novelty_faers_count" in row:
        row["novelty"] = {
            "score":            row.pop("novelty_score", 0.0),
            "in_fda_label":     bool(row.pop("novelty_in_fda_label", False)),
            "faers_count":      int(row.pop("novelty_faers_count", 0)),
            "internal_7d_count": 0,
        }
    return row


@router.get("/stats")
def signal_stats(project_id: str = Query(None)):
    """Aggregate counts by signal_type — used by dashboard metric cards."""
    query  = "SELECT signal_type, COUNT(*) as count FROM genomes WHERE 1=1"
    params: list = []
    if project_id:
        query += " AND project_id=?"; params.append(project_id)
    query += " GROUP BY signal_type"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return {r["signal_type"]: r["count"] for r in rows}


@router.get("/")
def list_signals(
    project_id:  str = Query(None),
    signal_type: str = Query(None),
    drug:        str = Query(None),
    symptom:     str = Query(None),
    source_type: str = Query(None),
    limit:       int = Query(50, le=200),
    offset:      int = Query(0),
):
    """List genomes with optional filters — used by Live Feed panel."""
    query  = "SELECT * FROM genomes WHERE 1=1"
    params: list = []
    if project_id:  query += " AND project_id=?";    params.append(project_id)
    if signal_type: query += " AND signal_type=?";   params.append(signal_type)
    if drug:        query += " AND drugs LIKE ?";     params.append(f"%{drug}%")
    if symptom:     query += " AND symptoms LIKE ?";  params.append(f"%{symptom}%")
    if source_type: query += " AND source_type=?";   params.append(source_type)
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [_parse(dict(r)) for r in rows]


@router.get("/{genome_id}")
def get_signal(genome_id: str):
    """Single genome by ID — used by genome detail panel."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM genomes WHERE genome_id=?", (genome_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Genome not found")
        return _parse(dict(row))