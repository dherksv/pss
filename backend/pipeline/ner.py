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
import spacy
from transformers import pipeline as hf_pipeline
from models.genome import Entities, GeoSignal

# Lazy references — nothing loads at import time
_bio_ner   = None
_nlp_spacy = None

def get_bio_ner():
    global _bio_ner
    if _bio_ner is None:
        print("Loading biomedical NER model...")
        _bio_ner = hf_pipeline(
            "token-classification",
            model="d4data/biomedical-ner-all",
            aggregation_strategy="simple"
        )
        print("NER model ready.")
    return _bio_ner

def get_spacy():
    global _nlp_spacy
    if _nlp_spacy is None:
        try:
            _nlp_spacy = spacy.load("en_core_web_sm")
            print("spaCy model ready.")
        except OSError:
            print("WARNING: spaCy model not found — skipping location extraction.")
            _nlp_spacy = False   # False means tried and failed, don't retry
    return _nlp_spacy if _nlp_spacy else None

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

        # BioBERT biomedical NER
        # Bio NER
        try:
            bio_results = get_bio_ner()(text[:512])
            for ent in bio_results:
                label = ent.get("entity_group", "").upper()
                word  = ent.get("word", "").strip()
                score = ent.get("score", 0.0)

                if score < 0.6 or len(word) < 2:
                    continue

                if "CHEM" in label or "DRUG" in label:
                    normalized = normalize_drug_name(word)
                    if normalized not in entities.drugs:
                        entities.drugs.append(normalized)

                elif "DISEASE" in label or "SYMPTOM" in label:
                    if word not in entities.symptoms:
                        entities.symptoms.append(word)

        except Exception as e:
            logger.warning(f"SciBERT NER failed (non-fatal): {e}")


        # spaCy NER
        try:
            nlp = get_spacy()
            if nlp:
                doc = nlp(text[:512])
                for ent in doc.ents:
                    if ent.label_ in ("GPE", "LOC") and ent.text not in entities.locations:
                        entities.locations.append(ent.text)
                    if ent.label_ == "ORG" and ent.text not in entities.institutions:
                        entities.institutions.append(ent.text)

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