"""
pipeline/ner.py - Named Entity Recognition | OWNER: Engineer B
Uses BioBERT for biomedical NER + spaCy for location/org extraction.
RxNorm normalizes drug names to canonical form.
"""
import requests
from transformers import pipeline as hf_pipeline
import spacy
from models.genome import Entities, GeoSignal

# Load models once at module level (expensive - do NOT reload per request)
bio_ner = hf_pipeline(
    "ner",
    model="allenai/scibert_scivocab_uncased",
    aggregation_strategy="simple"
)
nlp_spacy = spacy.load("en_core_web_sm")

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
        try:
            bio_results = bio_ner(text[:512])
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

        # spaCy for locations and organizations
        try:
            doc = nlp_spacy(text[:512])
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
