"""
pipeline/classifier.py - Signal type classifier | OWNER: Engineer B
Classifies each post into one of five signal types.
Uses Mental-RoBERTa for distress, rule+model hybrid for others.
"""
from transformers import pipeline as hf_pipeline
from models.genome import Entities

distress_clf = hf_pipeline(
    "text-classification",
    model="mental/mental-roberta-base"
)

MISINFORMATION_SIGNALS = [
    "miracle cure", "doctors dont want", "big pharma hiding",
    "natural cure", "100% effective", "guaranteed to cure",
    "they don't want you to know",
]

DISSATISFACTION_SIGNALS = [
    "worst doctor", "terrible hospital", "no one listened",
    "misdiagnosed", "wrong medication", "refused to treat",
    "ignored my symptoms", "didn't help at all",
]

class SignalClassifier:
    def classify(self, text: str, entities: Entities) -> str:
        """
        Returns one of:
        adverse_drug_reaction | distress | misinformation |
        treatment_dissatisfaction | general
        """
        lower = text.lower()

        # Distress — use Mental-RoBERTa
        try:
            result = distress_clf(text[:512])[0]
            if result["label"] != "no risk" and result["score"] > 0.75:
                return "distress"
        except Exception:
            pass

        # Misinformation — rule based
        if any(sig in lower for sig in MISINFORMATION_SIGNALS):
            return "misinformation"

        # Treatment dissatisfaction
        if any(sig in lower for sig in DISSATISFACTION_SIGNALS):
            return "treatment_dissatisfaction"

        # ADR — drug + symptom both present
        if entities.drugs and entities.symptoms:
            adr_signals = ["side effect","adverse","reaction","started taking",
                           "after taking","since taking","caused by"]
            if any(s in lower for s in adr_signals):
                return "adverse_drug_reaction"

        return "general"
