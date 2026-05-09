"""
storage/sqlite_store.py - SQLite persistence layer | OWNER: Engineer A
Stores genome metadata, projects, outbreaks, alerts.
ChromaDB (vector store) is in chroma_store.py — Engineer B owns that.
"""
import logging
import sqlite3, json, os
from datetime import datetime

DB_PATH = os.getenv("SQLITE_PATH", "/app/db/sentinel.db")


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _resolve(obj, path, default=None):
    """Resolve nested attributes or dict keys from a genome object."""
    if obj is None:
        return default
    if hasattr(obj, path):
        return getattr(obj, path)
    if isinstance(obj, dict):
        parts = path.split('.')
        value = obj
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value
    return default


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            keywords TEXT,
            sources TEXT,
            created_at TEXT,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS genomes (
            genome_id TEXT PRIMARY KEY,
            post_id TEXT,
            project_id TEXT,
            source TEXT,
            source_type TEXT,
            source_url TEXT,
            signal_type TEXT,
            sentiment_score REAL,
            distress_level REAL,
            confidence_score REAL,
            novelty_score REAL,
            novelty_in_fda_label INTEGER DEFAULT 0,
            novelty_faers_count INTEGER DEFAULT 0,
            pii_detected INTEGER,
            phi_detected INTEGER,
            cluster_id TEXT,
            drugs TEXT,
            symptoms TEXT,
            locations TEXT,
            explanation TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS outbreaks (
            outbreak_id TEXT PRIMARY KEY,
            trigger_drug TEXT,
            trigger_symptom TEXT,
            severity TEXT,
            genome_ids TEXT,
            source_count INTEGER,
            platform_count INTEGER,
            regions TEXT,
            summary TEXT,
            confidence REAL,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS seen_posts (
            post_id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            seen_at TEXT
        );
        """)

        # Migrate old genomes table schemas to preserve full novelty metadata.
        cols = [row[1] for row in conn.execute('PRAGMA table_info(genomes)').fetchall()]
        if 'novelty_in_fda_label' not in cols:
            conn.execute('ALTER TABLE genomes ADD COLUMN novelty_in_fda_label INTEGER DEFAULT 0')
        if 'novelty_faers_count' not in cols:
            conn.execute('ALTER TABLE genomes ADD COLUMN novelty_faers_count INTEGER DEFAULT 0')

    print("Database initialised.")


def save_genome(genome, project_id: str = "") -> bool:
    try:
        with get_conn() as conn:
            conn.execute("""
            INSERT OR REPLACE INTO genomes VALUES (
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
            )""", (
                _resolve(genome, "genome_id"),
                _resolve(genome, "post_id"),
                project_id,
                _resolve(genome, "source"),
                _resolve(genome, "source_type"),
                _resolve(genome, "source_url"),
                _resolve(genome, "signal_type"),
                _resolve(genome, "sentiment_score"),
                _resolve(genome, "distress_level"),
                _resolve(genome, "confidence_score"),
                _resolve(genome, "novelty.score", 0.0),
                int(bool(_resolve(genome, "novelty.in_fda_label", False))),
                int(_resolve(genome, "novelty.faers_count", 0)),
                int(bool(_resolve(genome, "pii_detected", False))),
                int(bool(_resolve(genome, "phi_detected", False))),
                _resolve(genome, "cluster_id"),
                json.dumps(_resolve(genome, "entities.drugs", [])),
                json.dumps(_resolve(genome, "entities.symptoms", [])),
                json.dumps(_resolve(genome, "entities.locations", [])),
                _resolve(genome, "explanation"),
                datetime.utcnow().isoformat(),
            ))
        return True
    except Exception as exc:
        logging.error("Failed to save genome to SQLite: %s", exc, exc_info=True)
        return False


def save_outbreak(outbreak):
    with get_conn() as conn:
        conn.execute("""
        INSERT OR REPLACE INTO outbreaks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            outbreak.outbreak_id, outbreak.trigger_drug,
            outbreak.trigger_symptom, outbreak.severity,
            json.dumps(outbreak.genome_ids), outbreak.source_count,
            outbreak.platform_count, json.dumps(outbreak.regions),
            outbreak.summary, outbreak.confidence,
            outbreak.created_at, outbreak.updated_at,
        ))


def get_active_projects() -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM projects WHERE is_active=1").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["keywords"] = json.loads(d.get("keywords") or "[]")
            d["sources"]  = json.loads(d.get("sources")  or "[]")
            result.append(d)
        return result


def get_recent_genomes(drug=None, symptom=None, since=None) -> list:
    query  = "SELECT * FROM genomes WHERE 1=1"
    params = []
    if drug:
        query += " AND drugs LIKE ?"; params.append(f"%{drug}%")
    if symptom:
        query += " AND symptoms LIKE ?"; params.append(f"%{symptom}%")
    if since:
        query += " AND created_at >= ?"; params.append(since.isoformat())
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def get_genomes_by_period(project_id=None, drug=None, since=None) -> list:
    query  = "SELECT * FROM genomes WHERE 1=1"
    params = []
    if project_id:
        query += " AND project_id=?"; params.append(project_id)
    if drug:
        query += " AND drugs LIKE ?"; params.append(f"%{drug}%")
    if since:
        query += " AND created_at >= ?"; params.append(since.isoformat())
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def mark_post_seen(post_id: str, source: str) -> None:
    """Mark a post as seen to avoid reprocessing."""
    with get_conn() as conn:
        conn.execute("""
        INSERT OR REPLACE INTO seen_posts VALUES (?, ?, ?)
        """, (post_id, source, datetime.utcnow().isoformat()))


def is_post_seen(post_id: str, source: str) -> bool:
    """Check if a post has been seen before."""
    with get_conn() as conn:
        row = conn.execute("""
        SELECT 1 FROM seen_posts WHERE post_id=? AND source=?
        """, (post_id, source)).fetchone()
        return row is not None
