"""
pipeline/relevance.py - Relevance filter | OWNER: Engineer B
Quick check before running expensive NLP models.
TODO: upgrade to sentence-transformer similarity check if time allows.
"""
MEDICAL_SIGNAL_TERMS = [
    "side effect", "adverse", "reaction", "symptom", "pain", "dose",
    "medication", "drug", "pill", "tablet", "injection", "prescribed",
    "doctor", "hospital", "nausea", "vomit", "dizzy", "rash", "fever",
    "die", "death", "died", "overdose", "allergy", "treatment",
    "withdrawal", "warning", "recall", "contaminated", "poisoning",
]

class RelevanceChecker:
    def is_relevant(self, text: str) -> bool:
        """
        Returns True if text contains at least one medical signal term.
        Fast keyword check — runs before any transformer model.
        TODO Engineer B: optionally replace with semantic similarity threshold.
        """
        lower = text.lower()
        return any(term in lower for term in MEDICAL_SIGNAL_TERMS)
