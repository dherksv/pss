"""
relevance.py — Step 2 of PipelineProcessor

Fast keyword-based relevance filter. Drops posts that are clearly
not health/drug related BEFORE expensive NLP models run.

Design: pure regex + keyword sets. No models. Must be <5ms per post.
Returns True if the post should continue through the pipeline.
"""

import re
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Must-have signals — post needs at least ONE of these to be relevant
# ---------------------------------------------------------------------------

_DRUG_TERMS = {
    # GLP-1 / diabetes drugs (demo-critical)
    "ozempic", "wegovy", "mounjaro", "trulicity", "victoza", "rybelsus",
    "semaglutide", "tirzepatide", "liraglutide", "dulaglutide",
    "metformin", "insulin", "glipizide", "januvia", "jardiance",
    # Common medications
    "ibuprofen", "acetaminophen", "paracetamol", "aspirin", "tylenol",
    "advil", "prednisone", "amoxicillin", "azithromycin", "zpack",
    "lisinopril", "atorvastatin", "lipitor", "metoprolol",
    "xarelto", "eliquis", "warfarin", "humira", "keytruda",
    "adderall", "ritalin", "xanax", "zoloft", "prozac", "lexapro",
    # Cough syrup (Scenario 2 demo)
    "cough syrup", "doc-1 max", "doc1max", "promethazine", "codeine syrup",
    "dextromethorphan", "robitussin",
    # Generic terms
    "medication", "medicine", "drug", "prescription", "pill", "tablet",
    "capsule", "dose", "dosage", "injection", "vaccine",
}

_HEALTH_TERMS = {
    # Symptoms (demo-critical)
    "hair loss", "alopecia", "nausea", "vomiting", "diarrhea",
    "fatigue", "headache", "dizziness", "rash", "chest pain",
    "shortness of breath", "abdominal pain", "weight loss", "weight gain",
    "respiratory failure", "seizure", "stroke", "anaphylaxis",
    # Health system
    "side effect", "adverse event", "adverse reaction", "allergy",
    "doctor", "physician", "hospital", "clinic", "pharmacist",
    "diagnosis", "treatment", "therapy", "surgery", "prescription",
    "patient", "symptom", "condition", "disease", "disorder",
    # FDA / safety
    "fda", "recall", "warning", "safety alert", "black box",
    "medwatch", "faers", "pharmacovigilance",
}

# ---------------------------------------------------------------------------
# Spam / noise patterns — discard immediately if matched
# ---------------------------------------------------------------------------

_SPAM_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        # Crypto/finance spam common on reddit
        r"\b(?:bitcoin|crypto|nft|token|coin|blockchain)\b",
        r"\b(?:buy|sell|invest|profit|returns?|trading)\b.{0,30}\b(?:now|today|fast)\b",
        # Low-quality signal
        r"^.{0,20}$",      # Too short (< 20 chars = useless)
        r"^[\W\s]+$",      # Only punctuation/whitespace
        # Pure promotional
        r"\b(?:click here|limited offer|discount code|promo code)\b",
    ]
]

# Minimum length for a post to be worth processing
MIN_LENGTH = 30


def is_relevant(text: str) -> bool:
    """
    Returns True if the post is likely health/drug related.
    Fast path: O(n) keyword scan. No models.
    """
    if not text or len(text.strip()) < MIN_LENGTH:
        return False

    # Spam check first (cheapest)
    for pattern in _SPAM_PATTERNS:
        if pattern.search(text):
            logger.debug("Relevance: spam pattern matched, dropping.")
            return False

    text_lower = text.lower()

    # Must contain at least one drug term OR one health term
    has_drug   = any(term in text_lower for term in _DRUG_TERMS)
    has_health = any(term in text_lower for term in _HEALTH_TERMS)

    if not (has_drug or has_health):
        logger.debug("Relevance: no drug/health terms found, dropping.")
        return False

    return True