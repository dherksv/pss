"""
classifier.py — Step 4 of PipelineProcessor

Determines signal_type for a genome. One of:
  - adverse_drug_reaction
  - distress
  - misinformation
  - treatment_dissatisfaction
  - general

Two-pass classification:
  Pass 1 — Rule-based heuristics (fast, high precision for clear cases)
  Pass 2 — Mental-RoBERTa distress model (for ambiguous/emotional posts)

The classifier also produces a confidence_score used downstream.

CRITICAL: All models lazy-loaded. Never at import time.
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy model loader
# ---------------------------------------------------------------------------

_distress_model = None


def _get_distress_model():
    global _distress_model
    if _distress_model is None:
        from transformers import pipeline
        logger.info("Loading distress classifier model (first call)...")
        _distress_model = pipeline(
            "text-classification",
            model="mental/mental-roberta-base",
        )
        logger.info("Distress classifier model loaded.")
    return _distress_model


# ---------------------------------------------------------------------------
# Rule sets — ordered by priority (most specific first)
# ---------------------------------------------------------------------------

# ADR triggers — explicit adverse effect language
_ADR_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bside[\s-]effect[s]?\b",
        r"\badverse[\s-]?(event|reaction|effect)\b",
        r"\bcaused?\s+(?:by|from|after)\b",
        r"\bstarted?\s+(?:taking|using|on)\b.{0,60}\b(?:and|then|now)\b",
        r"\bsince\s+(?:starting|taking|using|beginning)\b",
        r"\bafter\s+(?:taking|using|starting|switching)\b",
        r"\breaction\s+to\b",
        r"\bnot\s+(?:listed|documented|mentioned|on\s+the\s+label)\b",
        r"\bundocumented\b",
        r"\bunexpected\b.{0,40}\b(?:symptom|effect|reaction)\b",
    ]
]

# Misinfo triggers — false/dangerous medical claims
_MISINFO_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bcures?\b.{0,30}\b(?:cancer|diabetes|covid|hiv|aids)\b",
        r"\b(?:big\s+pharma|pharmaceutical\s+conspiracy)\b",
        r"\b(?:doctors|hospitals|fda)\s+(?:hiding|covering\s+up|lying)\b",
        r"\b(?:miracle|magic)\s+(?:cure|treatment|remedy)\b",
        r"\bdon'?t\s+(?:trust|believe)\s+(?:your\s+)?doctor\b",
        r"\b(?:natural|herbal)\s+(?:cure|treatment)\s+(?:for|of)\b",
        r"\bvaccine.{0,20}(?:cause|causes?|caused?)\b",
        r"\bgovernment.{0,20}(?:poison|kill|control)\b",
    ]
]

# Dissatisfaction triggers — complaints about treatment/drug/system
_DISSATISFACTION_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\b(?:not\s+working|doesn'?t\s+work|stopped\s+working)\b",
        r"\b(?:useless|ineffective|waste\s+of\s+(?:money|time))\b",
        r"\b(?:terrible|horrible|awful|worst)\s+(?:drug|medication|doctor|experience)\b",
        r"\b(?:switching|switched|changing)\s+(?:from|away\s+from)\b",
        r"\bno\s+(?:improvement|effect|change|difference)\b",
        r"\b(?:insurance|pharmacy|cost|price)\s+(?:denied|refused|too\s+expensive)\b",
        r"\b(?:can'?t\s+afford|too\s+expensive|price\s+gouging)\b",
        r"\bmy\s+doctor\s+(?:won'?t|refuses?|doesn'?t)\b",
        r"\bgave\s+up\s+on\b",
        r"\bquit(?:ting)?\s+(?:the\s+)?(?:medication|drug|treatment|pill)\b",
    ]
]

# Distress/crisis language
_DISTRESS_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\b(?:suicidal|want\s+to\s+die|kill\s+myself|end\s+(?:it|my\s+life))\b",
        r"\b(?:hopeless|worthless|can'?t\s+go\s+on)\b",
        r"\b(?:panic\s+attack|breaking\s+down|falling\s+apart)\b",
        r"\b(?:mental\s+breakdown|crisis)\b",
        r"\bcan'?t\s+(?:take|handle|cope\s+with)\s+(?:this|it|anymore)\b",
        r"\b(?:nobody\s+cares?|no\s+one\s+helps?|completely\s+alone)\b",
    ]
]

# Severity boosters — increase ADR confidence
_SEVERITY_BOOSTERS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\b(?:hospitalized?|emergency|ER|ICU|ambulance)\b",
        r"\b(?:severe|serious|life[\s-]threatening|critical)\b",
        r"\b(?:stopped?\s+breathing|cardiac|stroke|seizure)\b",
        r"\b(?:death|died|fatal|fatality|passed\s+away)\b",
    ]
]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ClassificationResult:
    signal_type:      str    # adverse_drug_reaction | distress | ...
    confidence_score: float  # 0.0 → 1.0
    rule_matched:     str    # which rule fired (for debugging/XAI)


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

class Classifier:
    """
    Classifies a post into a signal_type.
    Call .classify(text, ner_result) → ClassificationResult

    ner_result is passed in so we can use entity presence as signal
    (e.g. drugs + symptoms detected → strong ADR indicator).
    """

    def classify(self, text: str, ner_result=None) -> ClassificationResult:
        if not text or not text.strip():
            return ClassificationResult("general", 0.3, "empty_text")

        # ------------------------------------------------------------------
        # Pass 1 — Rule-based (fast path)
        # ------------------------------------------------------------------
        result = self._rule_based(text, ner_result)
        if result.confidence_score >= 0.75:
            return result

        # ------------------------------------------------------------------
        # Pass 2 — Model-based distress detection (for ambiguous posts)
        # ------------------------------------------------------------------
        distress_result = self._model_distress(text)

        # If model says distress with high confidence, override
        if (
            distress_result.signal_type == "distress"
            and distress_result.confidence_score > result.confidence_score
        ):
            return distress_result

        return result

    # ------------------------------------------------------------------
    # Rule-based classifier
    # ------------------------------------------------------------------

    def _rule_based(
        self, text: str, ner_result=None
    ) -> ClassificationResult:

        # Count pattern matches per category
        adr_hits          = sum(1 for p in _ADR_PATTERNS          if p.search(text))
        misinfo_hits      = sum(1 for p in _MISINFO_PATTERNS       if p.search(text))
        dissatisfied_hits = sum(1 for p in _DISSATISFACTION_PATTERNS if p.search(text))
        distress_hits     = sum(1 for p in _DISTRESS_PATTERNS      if p.search(text))
        severity_boost    = sum(1 for p in _SEVERITY_BOOSTERS      if p.search(text))

        # Entity presence boosts ADR confidence significantly
        has_drug    = bool(ner_result and ner_result.drugs)
        has_symptom = bool(ner_result and ner_result.symptoms)
        entity_adr_boost = (1 if has_drug else 0) + (1 if has_symptom else 0)

        # ------------------------------------------------------------------
        # Priority ordering (misinfo first — it's the most specific)
        # ------------------------------------------------------------------

        if misinfo_hits >= 1:
            conf = min(0.95, 0.60 + (misinfo_hits * 0.15))
            return ClassificationResult("misinformation", conf, "misinfo_pattern")

        if distress_hits >= 1:
            conf = min(0.95, 0.70 + (distress_hits * 0.10))
            return ClassificationResult("distress", conf, "distress_pattern")

        if adr_hits >= 1 or entity_adr_boost >= 2:
            # Both patterns AND entities → very high confidence
            conf = min(0.97, 0.55
                       + (adr_hits          * 0.12)
                       + (entity_adr_boost  * 0.10)
                       + (severity_boost    * 0.08))
            return ClassificationResult(
                "adverse_drug_reaction", conf, f"adr_pattern+entity_boost={entity_adr_boost}"
            )

        if dissatisfied_hits >= 1:
            conf = min(0.90, 0.55 + (dissatisfied_hits * 0.12))
            return ClassificationResult(
                "treatment_dissatisfaction", conf, "dissatisfaction_pattern"
            )

        # Low-confidence ADR: has drug+symptom entities but no clear ADR language
        if entity_adr_boost == 2:
            return ClassificationResult(
                "adverse_drug_reaction", 0.55, "entity_only_adr"
            )

        return ClassificationResult("general", 0.40, "no_pattern_match")

    # ------------------------------------------------------------------
    # Model-based distress detection
    # ------------------------------------------------------------------

    def _model_distress(self, text: str) -> ClassificationResult:
        try:
            model  = _get_distress_model()
            result = model(text[:512])[0]
            label  = result["label"].lower()
            score  = result["score"]

            is_distress = (
                "depression" in label
                or "anxiety"  in label
                or "stress"   in label
            ) and "not" not in label

            if is_distress and score > 0.65:
                return ClassificationResult(
                    "distress",
                    round(score, 4),
                    f"mental_roberta:{label}"
                )

        except Exception as e:
            logger.warning(f"Distress model failed in classifier: {e}")

        return ClassificationResult("general", 0.35, "model_fallback")


# ---------------------------------------------------------------------------
# Module singleton
# ---------------------------------------------------------------------------

_classifier_instance: Optional[Classifier] = None


def get_classifier() -> Classifier:
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = Classifier()
    return _classifier_instance