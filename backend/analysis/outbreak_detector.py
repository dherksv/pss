"""
analysis/outbreak_detector.py - Outbreak Pattern Detector | OWNER: Engineer B
Watches incoming genomes for three trigger conditions:
  1. Volume spike - same drug+symptom > threshold in time window
  2. Novelty convergence - multiple high-novelty genomes for same pair
  3. Cross-platform convergence - same signal on 3+ different platforms
"""
from datetime import datetime, timedelta
from models.genome import OutbreakRecord
from storage.sqlite_store import get_recent_genomes, save_outbreak

VOLUME_THRESHOLD    = 10   # posts in window
NOVELTY_THRESHOLD   = 0.7  # novelty score cutoff
PLATFORM_THRESHOLD  = 3    # distinct platforms
TIME_WINDOW_HOURS   = 6


class OutbreakDetector:
    def check(self, genome) -> OutbreakRecord | None:
        """
        Called after every genome is stored.
        Returns OutbreakRecord if a pattern is detected, else None.
        """
        if not genome.entities.drugs or not genome.entities.symptoms:
            return None

        drug    = genome.entities.drugs[0]
        symptom = genome.entities.symptoms[0]
        since   = datetime.utcnow() - timedelta(hours=TIME_WINDOW_HOURS)

        # Fetch recent genomes matching same drug+symptom
        recent = get_recent_genomes(drug=drug, symptom=symptom, since=since)

        # Condition 1 — Volume spike
        volume_triggered = len(recent) >= VOLUME_THRESHOLD

        # Condition 2 — Novelty convergence
        high_novelty = [g for g in recent if g.get("novelty_score", 0) >= NOVELTY_THRESHOLD]
        novelty_triggered = len(high_novelty) >= 3

        # Condition 3 — Cross-platform convergence
        platforms = set(g.get("source_type") for g in recent)
        platform_triggered = len(platforms) >= PLATFORM_THRESHOLD

        if not (volume_triggered or novelty_triggered or platform_triggered):
            return None

        # Determine severity
        triggers = sum([volume_triggered, novelty_triggered, platform_triggered])
        severity = {1: "watch", 2: "warning", 3: "alert"}.get(triggers, "watch")

        outbreak = OutbreakRecord(
            trigger_drug     = drug,
            trigger_symptom  = symptom,
            severity         = severity,
            genome_ids       = [g["genome_id"] for g in recent],
            source_count     = len(recent),
            platform_count   = len(platforms),
            regions          = list(set(
                loc for g in recent for loc in g.get("locations", [])
            )),
            confidence       = min(1.0, len(recent) / VOLUME_THRESHOLD),
            summary          = self._summarize(drug, symptom, recent, severity, platforms),
        )
        save_outbreak(outbreak)
        return outbreak

    def _summarize(self, drug, symptom, recent, severity, platforms):
        return (
            f"{len(recent)} users across {', '.join(platforms)} reported "
            f"{symptom} linked to {drug} in the last {TIME_WINDOW_HOURS} hours. "
            f"Severity: {severity.upper()}. "
            f"Cross-platform signal detected across {len(platforms)} platform(s)."
        )
