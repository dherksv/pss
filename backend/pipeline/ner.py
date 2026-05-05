"""
pipeline/ner.py - Named Entity Recognition | OWNER: Engineer B
Uses BioBERT for biomedical NER + spaCy for location/org extraction.
RxNorm normalizes drug names to canonical form.
"""
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


def normalize_drug_name(name: str) -> str:
    """Use NIH RxNorm API to normalize drug name. Free, no key needed."""
    try:
        resp = requests.get(RXNORM_URL, params={"name": name}, timeout=5)
        ids = resp.json().get("idGroup", {}).get("rxnormId", [])
        if ids:
            # Get canonical name
            detail = requests.get(
                f"https://rxnav.nlm.nih.gov/REST/rxcui/{ids[0]}/property.json",
                params={"propName": "RxNorm Name"}, timeout=5)
            props = detail.json().get("propConceptGroup", {}).get("propConcept", [])
            if props:
                return props[0].get("propValue", name)
    except Exception:
        pass
    return name


class NERExtractor:
    def extract(self, text: str, metadata: dict) -> tuple:
        entities = Entities()
        geo      = GeoSignal()

        # BioBERT biomedical NER
        # Bio NER
        try:
            bio_results = get_bio_ner()(text[:512])
            for ent in bio_results:
                label = ent.get("entity_group", "").upper()
                word  = ent.get("word", "").strip()
                if not word:
                    continue

                if "CHEM" in label or "DRUG" in label:
                    normalized = normalize_drug_name(word)
                    if normalized not in entities.drugs:
                        entities.drugs.append(normalized)

                elif "DISEASE" in label or "SYMPTOM" in label:
                    if word not in entities.symptoms:
                        entities.symptoms.append(word)

        except Exception as e:
            print(f"BioBERT NER error: {e}")


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
            print(f"spaCy NER error: {e}")

        # Geo signal
        geo.extracted_locations = entities.locations
        geo.subreddit_geo_proxy = metadata.get("geo_proxy", "")
        geo.confidence = 0.8 if entities.locations else 0.3

        return entities, geo
