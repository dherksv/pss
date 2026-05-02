"""
storage/sqlite_store.py - SQLite persistence layer | OWNER: Engineer A
Stores genome metadata, projects, outbreaks, alerts.
ChromaDB (vector store) is in chroma_store.py — Engineer B owns that.
"""
import sqlite3, json, os
from datetime import datetime

DB_PATH = os.getenv("SQLITE_PATH", "/app/db/sentinel.db")


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            genome_id TEXT,
            outbreak_id TEXT,
            alert_type TEXT,
            message TEXT,
            resolved INTEGER DEFAULT 0,
            created_at TEXT
        );
        """)
    print("Database initialised.")


def save_genome(genome, project_id: str = ""):
    with get_conn() as conn:
        conn.execute("""
        INSERT OR REPLACE INTO genomes VALUES (
            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
        )""", (
            genome.genome_id, genome.post_id, project_id,
            genome.source, genome.source_type, genome.source_url,
            genome.signal_type, genome.sentiment_score,
            genome.distress_level, genome.confidence_score,
            genome.novelty.score, int(genome.pii_detected),
            int(genome.phi_detected), genome.cluster_id,
            json.dumps(genome.entities.drugs),
            json.dumps(genome.entities.symptoms),
            json.dumps(genome.entities.locations),
            genome.explanation,
            datetime.utcnow().isoformat(),
        ))


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
        return [dict(r) for r in rows]


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
