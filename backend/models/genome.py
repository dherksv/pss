"""
genome.py - Signal Genome dataclass | OWNER: Engineer B
This is the atomic unit of the entire system.
Every component reads/writes this schema.
DO NOT change field names without team agreement.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
import uuid


@dataclass
class GeoSignal:
    extracted_locations: list = field(default_factory=list)
    subreddit_geo_proxy: str = ""
    google_trends_region: str = ""
    confidence: float = 0.0


@dataclass
class Entities:
    drugs: list      = field(default_factory=list)
    symptoms: list   = field(default_factory=list)
    conditions: list = field(default_factory=list)
    locations: list  = field(default_factory=list)
    institutions: list = field(default_factory=list)


@dataclass
class NoveltyScore:
    in_fda_label: bool        = False
    faers_count: int          = 0
    internal_7d_count: int    = 0
    score: float              = 0.0   # 0=known, 1=completely novel


@dataclass
class SignalGenome:
    # Identity
    genome_id: str         = field(default_factory=lambda: str(uuid.uuid4()))
    post_id: str           = ""
    created_at: str        = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Source
    source: str            = ""
    source_type: str       = ""
    source_url: str        = ""
    raw_text: str          = ""
    author: str            = ""
    post_timestamp: str    = ""

    # Extracted intelligence
    entities: Entities     = field(default_factory=Entities)
    geo: GeoSignal         = field(default_factory=GeoSignal)

    # Signal classification
    signal_type: str       = "unknown"
    # Options: adverse_drug_reaction | distress | misinformation | treatment_dissatisfaction | general

    # Scores
    sentiment_score: float = 0.0    # -1.0 (negative) to 1.0 (positive)
    distress_level: float  = 0.0    # 0.0 to 1.0
    confidence_score: float = 0.0   # model confidence 0.0 to 1.0
    novelty: NoveltyScore  = field(default_factory=NoveltyScore)

    # Safety flags
    pii_detected: bool     = False
    phi_detected: bool     = False
    pii_redacted_text: str = ""

    # XAI
    explanation: str       = ""

    # Outbreak linkage
    cluster_id: str        = None
    related_genome_ids: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


@dataclass
class OutbreakRecord:
    outbreak_id: str       = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str        = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str        = field(default_factory=lambda: datetime.utcnow().isoformat())

    # What triggered it
    trigger_drug: str      = ""
    trigger_symptom: str   = ""
    trigger_condition: str = ""

    # Severity: watch | warning | alert | critical
    severity: str          = "watch"

    # Linked genomes
    genome_ids: list       = field(default_factory=list)
    source_count: int      = 0
    platform_count: int    = 0

    # Geographic spread
    regions: list          = field(default_factory=list)

    # Summary
    summary: str           = ""
    confidence: float      = 0.0

    def to_dict(self):
        return asdict(self)
