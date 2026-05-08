"""
scorer.py — Step 5 of PipelineProcessor

Computes three scores for a genome:
  1. sentiment_score   (-1.0 to 1.0) via cardiffnlp/twitter-roberta
  2. distress_level    (0.0 to 1.0)  via mental/mental-roberta-base
  3. novelty_score     (0.0 to 1.0)  via FDA Label + FAERS cross-reference

Novelty formula:
  label_factor = 0.0 if symptom documented in FDA label, else 0.5
  faers_factor = max(0.0, 0.5 - (faers_count / 10_000))
  novelty_score = min(1.0, label_factor + faers_factor)

High novelty (>0.7) = potentially undocumented adverse signal.
"""

import logging
import os
import requests
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy model loaders
# ---------------------------------------------------------------------------

_sentiment_model = None
_distress_model  = None


def _get_transformers_cache_dir() -> str:
    return os.getenv("TRANSFORMERS_CACHE", os.getenv("HF_HOME", "./models_cache/hub"))


def _get_sentiment():
    global _sentiment_model
    if _sentiment_model is None:
        from transformers import pipeline
        cache_dir = _get_transformers_cache_dir()
        os.makedirs(cache_dir, exist_ok=True)
        logger.info("Loading sentiment model (first call)...")
        _sentiment_model = pipeline(
            "sentiment-analysis",
            model="cardiffnlp/twitter-roberta-base-sentiment-latest",
            cache_dir=cache_dir,
            local_files_only=True,
        )
        logger.info("Sentiment model loaded.")
    return _sentiment_model


def _get_distress():
    global _distress_model
    if _distress_model is None:
        from transformers import pipeline
        cache_dir = _get_transformers_cache_dir()
        os.makedirs(cache_dir, exist_ok=True)
        logger.info("Loading distress model (first call)...")
        _distress_model = pipeline(
            "text-classification",
            model="j-hartmann/emotion-english-distilroberta-base",
            cache_dir=cache_dir,
            local_files_only=True,
        )
        logger.info("Distress model loaded.")
    return _distress_model


# ---------------------------------------------------------------------------
# FDA API helpers
# ---------------------------------------------------------------------------

FDA_LABEL_URL = "https://api.fda.gov/drug/label.json"
FDA_FAERS_URL = "https://api.fda.gov/drug/event.json"

# In-process cache: (drug, symptom) → (in_label: bool, faers_count: int)
_fda_cache: dict[tuple, tuple] = {}


def _check_fda_label(drug: str, symptom: str) -> bool:
    """
    Returns True if the symptom appears in the FDA drug label for this drug.
    Checks adverse_reactions and warnings sections.
    """
    try:
        resp = requests.get(
            FDA_LABEL_URL,
            params={
                "search": f'openfda.brand_name:"{drug}"',
                "limit": 1,
            },
            timeout=5,
        )
        if resp.status_code != 200:
            return False

        data = resp.json()
        results = data.get("results", [])
        if not results:
            return False

        label = results[0]
        # Sections that document adverse effects
        sections_to_check = [
            "adverse_reactions",
            "warnings",
            "warnings_and_cautions",
            "boxed_warning",
            "precautions",
            "information_for_patients",
        ]

        symptom_lower = symptom.lower()
        for section in sections_to_check:
            content = label.get(section, [])
            if isinstance(content, list):
                content = " ".join(content)
            if symptom_lower in content.lower():
                return True

        return False

    except requests.RequestException as e:
        logger.warning(f"FDA label check failed for {drug}/{symptom}: {e}")
        return False  # Assume not in label → higher novelty (conservative)


def _get_faers_count(drug: str, symptom: str) -> int:
    """
    Returns the count of historical FAERS reports for this drug+symptom pair.
    Returns 0 on any failure (conservative — gives higher novelty score).
    """
    try:
        search = (
            f'patient.drug.medicinalproduct:"{drug}"'
            f'+AND+patient.reaction.reactionmeddrapt:"{symptom}"'
        )
        resp = requests.get(
            FDA_FAERS_URL,
            params={"search": search, "limit": 1},
            timeout=5,
        )
        if resp.status_code != 200:
            return 0

        data = resp.json()
        # FAERS returns total count in meta
        return data.get("meta", {}).get("results", {}).get("total", 0)

    except requests.RequestException as e:
        logger.warning(f"FAERS count failed for {drug}/{symptom}: {e}")
        return 0


def _compute_novelty(drug: str, symptom: str) -> dict:
    """
    Cross-reference drug+symptom against FDA sources.
    Returns dict matching the genome's novelty sub-object (minus internal_7d_count).
    """
    cache_key = (drug.lower(), symptom.lower())

    if cache_key not in _fda_cache:
        in_label    = _check_fda_label(drug, symptom)
        faers_count = _get_faers_count(drug, symptom)
        _fda_cache[cache_key] = (in_label, faers_count)
    else:
        in_label, faers_count = _fda_cache[cache_key]

    label_factor  = 0.0 if in_label else 0.5
    faers_factor  = max(0.0, 0.5 - (faers_count / 10_000))
    novelty_score = min(1.0, label_factor + faers_factor)

    return {
        "in_fda_label":      in_label,
        "faers_count":       faers_count,
        "internal_7d_count": 0,  # filled by OutbreakDetector later
        "score":             round(novelty_score, 4),
    }


# ---------------------------------------------------------------------------
# Sentiment scoring
# ---------------------------------------------------------------------------

# Map cardiffnlp labels → -1.0 to 1.0
_SENTIMENT_MAP = {
    "LABEL_0": -1.0,   # negative
    "LABEL_1":  0.0,   # neutral
    "LABEL_2":  1.0,   # positive
    # Some versions of the model use these labels:
    "negative": -1.0,
    "neutral":   0.0,
    "positive":  1.0,
}


def _score_sentiment(text: str) -> float:
    """Returns sentiment score from -1.0 (negative) to 1.0 (positive)."""
    try:
        model   = _get_sentiment()
        result  = model(text[:512])[0]  # truncate to model max
        label   = result["label"]
        raw_score = result["score"]  # confidence 0→1

        # Map label to direction, then scale by confidence
        direction = _SENTIMENT_MAP.get(label, 0.0)
        if direction != 0.0:
            return round(direction * raw_score, 4)
        return 0.0

    except Exception as e:
        logger.warning(f"Sentiment scoring failed: {e}")
        return 0.0


# ---------------------------------------------------------------------------
# Distress scoring
# ---------------------------------------------------------------------------

def _score_distress(text: str) -> float:
    """
    Returns distress level 0.0 to 1.0.
    mental-roberta-base outputs: not depression / depression labels.
    We map depression label confidence → distress score.
    """
    try:
        model  = _get_distress()
        result = model(text[:512])[0]
        label  = result["label"].lower()
        score  = result["score"]

        # Any non-normal/non-neutral label indicates distress
        if "depression" in label or "anxiety" in label or "stress" in label:
            return round(score, 4)
        # If model says "not depression" with high confidence → low distress
        return round(1.0 - score, 4) if "not" in label else 0.0

    except Exception as e:
        logger.warning(f"Distress scoring failed: {e}")
        return 0.0


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ScoreResult:
    sentiment_score:   float
    distress_level:    float
    confidence_score:  float
    novelty:           dict   # matches genome.novelty schema


# ---------------------------------------------------------------------------
# Main scorer
# ---------------------------------------------------------------------------

class Scorer:
    """
    Call .score(text, drugs, symptoms) → ScoreResult
    drugs and symptoms come from NERResult.
    """

    def score(
        self,
        text:     str,
        drugs:    list[str],
        symptoms: list[str],
    ) -> ScoreResult:

        sentiment = _score_sentiment(text)
        distress  = _score_distress(text)

        # Confidence = average of absolute sentiment + (1 - distress neutrality)
        # Simple heuristic: how strongly the model committed to any label
        confidence = round(
            min(1.0, (abs(sentiment) + distress) / 2 + 0.3),
            4
        )

        # Novelty: use first drug+symptom pair (most prominent signal)
        novelty = {
            "in_fda_label":      False,
            "faers_count":       0,
            "internal_7d_count": 0,
            "score":             0.5,  # default mid-novelty
        }

        if drugs and symptoms:
            # Try primary drug against primary symptom
            # Also try generic name from rxnorm if different
            primary_drug    = drugs[0]
            primary_symptom = symptoms[0]
            novelty = _compute_novelty(primary_drug, primary_symptom)

            # If novelty is low (symptom known), try other symptom combos
            if novelty["score"] < 0.5 and len(symptoms) > 1:
                for sym in symptoms[1:]:
                    candidate = _compute_novelty(primary_drug, sym)
                    if candidate["score"] > novelty["score"]:
                        novelty = candidate
                        break

        return ScoreResult(
            sentiment_score=sentiment,
            distress_level=distress,
            confidence_score=confidence,
            novelty=novelty,
        )


# Module-level singleton
_scorer_instance: Optional[Scorer] = None


def get_scorer() -> Scorer:
    global _scorer_instance
    if _scorer_instance is None:
        _scorer_instance = Scorer()
    return _scorer_instance