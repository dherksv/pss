"""
pipeline/pii_scanner.py - PII/PHI detection | OWNER: Engineer B
Runs BEFORE any other pipeline step. Uses spaCy + regex patterns.
"""
import re
import spacy
from models.genome import SignalGenome

# Load lightweight spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

# Regex patterns for PHI
PHI_PATTERNS = {
    "email":   re.compile(r"\b[\w.+-]+@[\w-]+\.[a-z]{2,}\b", re.I),
    "phone":   re.compile(r"\b(\+?\d[\d\s\-().]{7,14}\d)\b"),
    "ssn":     re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "dob":     re.compile(r"\b(born|DOB|date of birth)[:\s]+\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", re.I),
    "mrn":     re.compile(r"\bMRN[:\s]*\d{5,}\b", re.I),
}


class PIIScanner:
    def scan(self, genome: SignalGenome) -> SignalGenome:
        text = genome.raw_text
        redacted = text
        pii_found = False
        phi_found = False

        # spaCy NER for PERSON entities
        doc = nlp(text[:512])  # cap for performance
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                redacted = redacted.replace(ent.text, "[NAME]")
                pii_found = True

        # Regex PHI patterns
        for label, pattern in PHI_PATTERNS.items():
            if pattern.search(redacted):
                redacted = pattern.sub(f"[{label.upper()}]", redacted)
                phi_found = True

        genome.pii_detected     = pii_found
        genome.phi_detected     = phi_found
        genome.pii_redacted_text = redacted if (pii_found or phi_found) else ""
        return genome
