"""
pipeline/classifier.py - Signal type classifier | OWNER: Engineer B
ALL models lazy-loaded — never at module import level.
"""
from models.genome import Entities

# Lazy reference — loads on first call only
_distress_clf = None

MISINFORMATION_SIGNALS = [
    "miracle cure", "doctors dont want", "big pharma hiding",
    "natural cure", "100% effective", "guaranteed to cure",
    "they don't want you to know",
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

ADR_SIGNALS = [
    "side effect", "adverse", "reaction", "started taking",
    "after taking", "since taking", "caused by", "because of the",
]


def get_distress_clf():
    global _distress_clf
    if _distress_clf is None:
        from transformers import pipeline as hf_pipeline
        print("Loading distress classifier...")
        try:
            _distress_clf = hf_pipeline(
                "text-classification",
                model="j-hartmann/emotion-english-distilroberta-base",
                return_all_scores=True,
            )
            print("Distress classifier ready.")
        except Exception as e:
            print(f"WARNING: Could not load distress model: {e}")
            _distress_clf = False   # mark as failed, don't retry
    return _distress_clf if _distress_clf else None


class SignalClassifier:
    def classify(self, text: str, entities: Entities) -> str:
        """
        Returns one of:
        adverse_drug_reaction | distress | misinformation |
        treatment_dissatisfaction | general
        """
        lower = text.lower()

        # Distress detection — use emotion model if available
        clf = get_distress_clf()
        if clf:
            try:
                results = clf(text[:512])[0]
                # j-hartmann model returns scores for: anger, disgust,
                # fear, joy, neutral, sadness, surprise
                score_map = {r["label"]: r["score"] for r in results}
                distress_score = (
                    score_map.get("sadness", 0) +
                    score_map.get("fear", 0)
                )
                if distress_score > 0.6:
                    return "distress"
            except Exception as e:
                print(f"Distress classification error: {e}")

        # Misinformation — rule based
        if any(sig in lower for sig in MISINFORMATION_SIGNALS):
            return "misinformation"

        # Treatment dissatisfaction — rule based
        if any(sig in lower for sig in DISSATISFACTION_SIGNALS):
            return "treatment_dissatisfaction"

        # ADR — drug + symptom + adr language
        if entities.drugs and entities.symptoms:
            if any(s in lower for s in ADR_SIGNALS):
                return "adverse_drug_reaction"

        return "general"
