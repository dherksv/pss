"""
ner.py — Step 3 of PipelineProcessor

Named Entity Recognition for biomedical text.

Two-model stack:
  Primary  — allenai/scibert_scivocab_uncased (HuggingFace, offline from cache)
  Fallback — spaCy en_core_web_sm (catches locations, orgs, persons)

RxNorm normalization: drug names are sent to RxNorm REST API to get
canonical names (e.g. "Ozempic" → "semaglutide"). This enriches the genome
and makes FDA cross-reference in scorer.py more reliable.

All models are lazy-loaded. See CRITICAL note in pii_scanner.py.
"""

import re
import logging
import requests
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy model loader — SciBERT NER
# ---------------------------------------------------------------------------

_bio_ner = None


def _get_bio_ner():
    global _bio_ner
    if _bio_ner is None:
        from transformers import pipeline
        logger.info("Loading SciBERT NER model (first call)...")
        _bio_ner = pipeline(
            "ner",
            model="allenai/scibert_scivocab_uncased",
            aggregation_strategy="simple",
            # Uses TRANSFORMERS_CACHE env var automatically
        )
        logger.info("SciBERT NER loaded.")
    return _bio_ner


# Lazy spaCy (shared with pii_scanner but we keep independent singleton
# so each module is self-contained)
_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        import spacy
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


# ---------------------------------------------------------------------------
# Domain keyword lists — fast pre/post filter
# ---------------------------------------------------------------------------

# Known drug brand names — supplement SciBERT when it misses trade names
DRUG_KEYWORDS = {
    "ozempic", "wegovy", "mounjaro", "trulicity", "victoza", "rybelsus",
    "metformin", "insulin", "humira", "keytruda", "dupixent", "xarelto",
    "eliquis", "lipitor", "atorvastatin", "lisinopril", "amlodipine",
    "semaglutide", "tirzepatide", "liraglutide", "dulaglutide",
    "cough syrup", "doc-1 max", "doc1max", "promethazine", "codeine",
    "ibuprofen", "acetaminophen", "paracetamol", "aspirin", "prednisone",
    "amoxicillin", "azithromycin", "doxycycline",
}

# Symptom / adverse effect keywords
SYMPTOM_KEYWORDS = {
    "hair loss", "alopecia", "nausea", "vomiting", "diarrhea", "diarrhoea",
    "fatigue", "headache", "dizziness", "rash", "itching", "pruritus",
    "chest pain", "palpitations", "shortness of breath", "dyspnea",
    "abdominal pain", "stomach pain", "cramps", "bloating", "constipation",
    "insomnia", "anxiety", "depression", "suicidal", "weight loss",
    "weight gain", "swelling", "edema", "numbness", "tingling",
    "vision changes", "blurred vision", "liver damage", "jaundice",
    "kidney failure", "renal failure", "respiratory failure",
    "anaphylaxis", "allergic reaction", "seizure", "stroke", "heart attack",
    "pancreatitis", "thyroid", "cancer", "tumor",
}

# Medical conditions
CONDITION_KEYWORDS = {
    "diabetes", "type 2 diabetes", "type 1 diabetes", "obesity",
    "hypertension", "high blood pressure", "hyperlipidemia", "cholesterol",
    "asthma", "copd", "heart disease", "atrial fibrillation",
    "depression", "anxiety", "bipolar", "schizophrenia",
    "arthritis", "rheumatoid", "lupus", "multiple sclerosis",
    "parkinson", "alzheimer", "dementia", "epilepsy",
    "hypothyroidism", "hyperthyroidism", "thyroiditis",
    "crohn", "ulcerative colitis", "ibd", "celiac",
    "psoriasis", "eczema", "dermatitis",
}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class NERResult:
    drugs:          list[str] = field(default_factory=list)
    symptoms:       list[str] = field(default_factory=list)
    conditions:     list[str] = field(default_factory=list)
    locations:      list[str] = field(default_factory=list)
    institutions:   list[str] = field(default_factory=list)
    rxnorm_map:     dict[str, str] = field(default_factory=dict)  # brand → generic


# ---------------------------------------------------------------------------
# RxNorm normalization
# ---------------------------------------------------------------------------

_rxnorm_cache: dict[str, Optional[str]] = {}   # simple in-process cache

RXNORM_URL = "https://rxnav.nlm.nih.gov/REST/rxcui.json"


def _normalize_drug_rxnorm(drug_name: str) -> Optional[str]:
    """
    Call RxNorm API to get the canonical/generic name for a drug.
    Returns normalized name, or None if not found.
    Results are cached in-process (drugs repeat a lot).
    """
    key = drug_name.lower().strip()
    if key in _rxnorm_cache:
        return _rxnorm_cache[key]

    try:
        resp = requests.get(
            RXNORM_URL,
            params={"name": drug_name},
            timeout=3,  # fast timeout — non-critical path
        )
        if resp.status_code == 200:
            data = resp.json()
            rxcui = data.get("idGroup", {}).get("rxnormId", [])
            if rxcui:
                # Get the actual name for this rxcui
                name_resp = requests.get(
                    f"https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui[0]}/properties.json",
                    timeout=3,
                )
                if name_resp.status_code == 200:
                    props = name_resp.json().get("properties", {})
                    canonical = props.get("name")
                    _rxnorm_cache[key] = canonical
                    return canonical
    except requests.RequestException as e:
        logger.debug(f"RxNorm lookup failed for '{drug_name}': {e}")

    _rxnorm_cache[key] = None
    return None


# ---------------------------------------------------------------------------
# Core NER extractor
# ---------------------------------------------------------------------------

class NERExtractor:
    """
    Extracts biomedical entities from text.
    Call .extract(text) → NERResult
    """

    def extract(self, text: str) -> NERResult:
        result = NERResult()

        if not text or not text.strip():
            return result

        text_lower = text.lower()

        # ------------------------------------------------------------------
        # Step A — Keyword matching (fast, high recall for known entities)
        # ------------------------------------------------------------------
        self._keyword_match(text_lower, result)

        # ------------------------------------------------------------------
        # Step B — SciBERT NER (catches novel/unknown biomedical terms)
        # ------------------------------------------------------------------
        self._scibert_extract(text, result)

        # ------------------------------------------------------------------
        # Step C — spaCy NER (locations, institutions)
        # ------------------------------------------------------------------
        self._spacy_extract(text, result)

        # ------------------------------------------------------------------
        # Step D — RxNorm normalization for all found drugs
        # ------------------------------------------------------------------
        self._rxnorm_normalize(result)

        # Deduplicate and clean all lists
        result.drugs        = self._clean(result.drugs)
        result.symptoms     = self._clean(result.symptoms)
        result.conditions   = self._clean(result.conditions)
        result.locations    = self._clean(result.locations)
        result.institutions = self._clean(result.institutions)

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _keyword_match(self, text_lower: str, result: NERResult):
        """Scan for known keywords (multi-word phrases first, then single)."""
        # Sort by length desc so "hair loss" matches before "hair"
        for phrase in sorted(DRUG_KEYWORDS, key=len, reverse=True):
            if phrase in text_lower:
                result.drugs.append(phrase)
                # Remove matched region to avoid double-counting
                text_lower = text_lower.replace(phrase, " ", 1)

        for phrase in sorted(SYMPTOM_KEYWORDS, key=len, reverse=True):
            if phrase in text_lower:
                result.symptoms.append(phrase)
                text_lower = text_lower.replace(phrase, " ", 1)

        for phrase in sorted(CONDITION_KEYWORDS, key=len, reverse=True):
            if phrase in text_lower:
                result.conditions.append(phrase)
                text_lower = text_lower.replace(phrase, " ", 1)

    def _scibert_extract(self, text: str, result: NERResult):
        """Run SciBERT NER and map entity types to our schema."""
        try:
            ner = _get_bio_ner()
            entities = ner(text[:512])  # SciBERT max token length guard

            for ent in entities:
                label = ent.get("entity_group", "").upper()
                word  = ent.get("word", "").strip()
                score = ent.get("score", 0.0)

                if score < 0.6 or len(word) < 2:
                    continue

                # SciBERT uses generic labels — map to our schema heuristically
                if label in ("DRUG", "CHEMICAL", "MEDICATION"):
                    result.drugs.append(word)
                elif label in ("DISEASE", "SYMPTOM", "SIGN_SYMPTOM", "ADR"):
                    result.symptoms.append(word)
                elif label in ("CONDITION", "DISORDER"):
                    result.conditions.append(word)
                else:
                    # Unknown label — apply heuristic: short all-caps = drug abbrev
                    if word.isupper() and 3 <= len(word) <= 8:
                        result.drugs.append(word)

        except Exception as e:
            logger.warning(f"SciBERT NER failed (non-fatal): {e}")

    def _spacy_extract(self, text: str, result: NERResult):
        """Use spaCy to catch locations and institutions."""
        try:
            nlp = _get_nlp()
            doc = nlp(text[:1000])  # spaCy limit guard

            for ent in doc.ents:
                if ent.label_ in ("GPE", "LOC", "FAC"):
                    result.locations.append(ent.text)
                elif ent.label_ == "ORG":
                    # Filter: likely medical institution
                    if any(kw in ent.text.lower() for kw in
                           ("hospital", "clinic", "pharma", "health",
                            "medical", "fda", "cdc", "who", "lab")):
                        result.institutions.append(ent.text)
        except Exception as e:
            logger.warning(f"spaCy extraction failed (non-fatal): {e}")

    def _rxnorm_normalize(self, result: NERResult):
        """
        For each drug found, query RxNorm for canonical name.
        Populates result.rxnorm_map and adds generic names to result.drugs.
        """
        normalized = []
        for drug in result.drugs:
            canonical = _normalize_drug_rxnorm(drug)
            if canonical and canonical.lower() != drug.lower():
                result.rxnorm_map[drug] = canonical
                normalized.append(canonical)
        result.drugs.extend(normalized)

    @staticmethod
    def _clean(items: list[str]) -> list[str]:
        """Deduplicate, strip, lowercase, remove empties."""
        seen = set()
        out  = []
        for item in items:
            item = item.strip().lower()
            if item and item not in seen:
                seen.add(item)
                out.append(item)
        return out


# Module-level singleton
_ner_instance: Optional[NERExtractor] = None


def get_ner_extractor() -> NERExtractor:
    global _ner_instance
    if _ner_instance is None:
        _ner_instance = NERExtractor()
    return _ner_instance