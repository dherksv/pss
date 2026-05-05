"""
pipeline/pii_scanner.py - PII/PHI detection | OWNER: Engineer B
"""
import re
from models.genome import SignalGenome

# Lazy reference — spaCy loaded only when first needed
_nlp = None

PHI_PATTERNS = {
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b", re.I),
    "phone": re.compile(r"\b(\+?\d[\d\s\-().]{7,14}\d)\b"),
    "ssn":   re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "dob":   re.compile(r"\b(born|DOB|date of birth)[:\s]+\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", re.I),
    "mrn":   re.compile(r"\bMRN[:\s]*\d{5,}\b", re.I),
}


def get_nlp():
    global _nlp
    if _nlp is None:
        import spacy
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            # Model not installed — skip NER, regex only
            print("WARNING: en_core_web_sm not found. Running regex-only PII scan.")
            _nlp = None
    return _nlp


class PIIScanner:
    def scan(self, genome: SignalGenome) -> SignalGenome:
        text      = genome.raw_text
        redacted  = text
        pii_found = False
        phi_found = False

        # spaCy person detection — only if model available
        nlp = get_nlp()
        if nlp:
            try:
                for ent in nlp(text[:512]).ents:
                    if ent.label_ == "PERSON":
                        redacted  = redacted.replace(ent.text, "[NAME]")
                        pii_found = True
            except Exception as e:
                print(f"spaCy error: {e}")

        # Regex PHI — always runs, no model needed
        for label, pattern in PHI_PATTERNS.items():
            if pattern.search(redacted):
                redacted  = pattern.sub(f"[{label.upper()}]", redacted)
                phi_found = True

        genome.pii_detected      = pii_found
        genome.phi_detected      = phi_found
        genome.pii_redacted_text = redacted if (pii_found or phi_found) else ""
        return genome