"""
outbreak_detector.py — Pattern detection over Signal Genomes

Watches ChromaDB for 3 trigger conditions within a 6-hour window:

  Condition 1 — Volume:   ≥10 posts for same drug+symptom pair
  Condition 2 — Novelty:  ≥3 high-novelty (>0.7) genomes for same pair  
  Condition 3 — Platform: same signal on 3+ distinct source_types

Severity mapping:
  1 trigger → "watch"
  2 triggers → "warning"
  3 triggers → "alert"

An OutbreakAlert is emitted when ≥1 condition fires.
Engineer C's WebSocket layer listens for these alerts.
"""

import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from storage.chroma_store import get_chroma_store

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

TIME_WINDOW_HOURS  = 6
VOLUME_THRESHOLD   = 10
NOVELTY_THRESHOLD  = 0.7
NOVELTY_MIN_COUNT  = 3   # need ≥3 high-novelty genomes to trigger
PLATFORM_THRESHOLD = 3

SEVERITY_MAP = {
    1: "watch",
    2: "warning",
    3: "alert",
}


# ---------------------------------------------------------------------------
# Outbreak alert dataclass
# ---------------------------------------------------------------------------

@dataclass
class OutbreakAlert:
    alert_id:          str
    created_at:        str
    drug:              str
    symptom:           str
    severity:          str                  # watch | warning | alert
    trigger_count:     int                  # 1 | 2 | 3
    conditions_fired:  list[str]            # ["volume", "novelty", "platform"]
    genome_count:      int                  # total matching genomes in window
    platforms:         list[str]            # distinct source_types seen
    novelty_scores:    list[float]          # novelty scores of matching genomes
    genome_ids:        list[str]            # IDs of contributing genomes
    summary:           str                  # human readable


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class OutbreakDetector:
    """
    Call .check(drug, symptom) after each genome is stored.
    Returns OutbreakAlert if conditions are met, else None.

    Typical usage in PipelineProcessor:
        alert = detector.check(genome.entities.drugs[0],
                               genome.entities.symptoms[0])
        if alert:
            await emit_alert(alert)
    """

    def __init__(self):
        self._store = get_chroma_store()

    def check(
        self,
        drug:    str,
        symptom: str,
    ) -> Optional[OutbreakAlert]:
        """
        Query ChromaDB for recent genomes matching this drug+symptom pair
        and evaluate all 3 trigger conditions.
        """
        if not drug or not symptom:
            return None

        # Fetch recent matching genomes from ChromaDB
        recent = self._store.query_by_drug_symptom(
            drug=drug,
            symptom=symptom,
            hours=TIME_WINDOW_HOURS,
        )

        if not recent:
            return None

        # ------------------------------------------------------------------
        # Evaluate conditions
        # ------------------------------------------------------------------

        # Condition 1 — Volume
        volume_triggered = len(recent) >= VOLUME_THRESHOLD

        # Condition 2 — Novelty convergence
        high_novelty = [
            g for g in recent
            if float(g.get("novelty_score", 0)) >= NOVELTY_THRESHOLD
        ]
        novelty_triggered = len(high_novelty) >= NOVELTY_MIN_COUNT

        # Condition 3 — Cross-platform
        platforms = list(set(
            g.get("source_type", "unknown") for g in recent
        ))
        platform_triggered = len(platforms) >= PLATFORM_THRESHOLD

        # ------------------------------------------------------------------
        # Build alert if any condition fired
        # ------------------------------------------------------------------
        conditions_fired = []
        if volume_triggered:   conditions_fired.append("volume")
        if novelty_triggered:  conditions_fired.append("novelty")
        if platform_triggered: conditions_fired.append("platform")

        trigger_count = len(conditions_fired)

        if trigger_count == 0:
            logger.debug(
                f"No outbreak conditions met for {drug}/{symptom} "
                f"({len(recent)} genomes in window)"
            )
            return None

        severity = SEVERITY_MAP.get(trigger_count, "watch")

        novelty_scores = [
            float(g.get("novelty_score", 0)) for g in recent
        ]
        genome_ids = [
            g.get("genome_id", "") for g in recent
        ]

        summary = self._build_summary(
            drug, symptom, severity, trigger_count,
            conditions_fired, len(recent), platforms, novelty_scores,
        )

        alert = OutbreakAlert(
            alert_id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
            drug=drug,
            symptom=symptom,
            severity=severity,
            trigger_count=trigger_count,
            conditions_fired=conditions_fired,
            genome_count=len(recent),
            platforms=platforms,
            novelty_scores=novelty_scores,
            genome_ids=genome_ids,
            summary=summary,
        )

        logger.warning(
            f"🚨 OUTBREAK {severity.upper()}: {drug} / {symptom} | "
            f"Triggers: {conditions_fired} | Genomes: {len(recent)}"
        )
        return alert

    def batch_check(self, genomes: list) -> list[OutbreakAlert]:
        """
        Check multiple drug+symptom pairs (e.g. on startup or scheduled scan).
        Deduplicates pairs before checking.
        """
        seen   = set()
        alerts = []

        for genome in genomes:
            try:
                drugs    = genome.entities.drugs    if hasattr(genome, 'entities') else genome.get('entities', {}).get('drugs', [])
                symptoms = genome.entities.symptoms if hasattr(genome, 'entities') else genome.get('entities', {}).get('symptoms', [])
                if not drugs or not symptoms:
                    continue
                pair = (drugs[0].lower(), symptoms[0].lower())
                if pair in seen:
                    continue
                seen.add(pair)
                alert = self.check(*pair)
                if alert:
                    alerts.append(alert)
            except Exception as e:
                logger.warning(f"batch_check error: {e}")

        return alerts

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_summary(
        drug, symptom, severity, trigger_count,
        conditions, genome_count, platforms, novelty_scores,
    ) -> str:
        avg_novelty = (
            sum(novelty_scores) / len(novelty_scores)
            if novelty_scores else 0.0
        )
        platform_str = ", ".join(platforms) if platforms else "unknown"
        condition_str = " + ".join(conditions)

        return (
            f"[{severity.upper()}] Potential outbreak signal detected: "
            f"{drug} associated with {symptom}. "
            f"{genome_count} posts in the last 6 hours across {platform_str}. "
            f"Triggered by: {condition_str}. "
            f"Average novelty score: {avg_novelty:.2f}. "
            f"{'⚠️ High novelty — may be undocumented adverse effect.' if avg_novelty > 0.7 else ''}"
        )


# Module singleton
_detector_instance: Optional[OutbreakDetector] = None


def get_outbreak_detector() -> OutbreakDetector:
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = OutbreakDetector()
    return _detector_instance