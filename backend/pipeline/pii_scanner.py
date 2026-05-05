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

# PHI-specific patterns (HIPAA-sensitive beyond generic PII)
_PHI_PATTERNS = {
    "health_plan_id": re.compile(
        r"\b(?:insurance\s*id|member\s*id|policy\s*#?)[:\s]*[A-Z0-9\-]{6,20}\b",
        re.IGNORECASE
    ),
    "npi":            re.compile(
        r"\b(?:npi)[:\s]*\d{10}\b",
        re.IGNORECASE
    ),
    "dea_number":     re.compile(
        r"\b[A-Z]{2}\d{7}\b"   # DEA registrant number format
    ),
}

# Replacement tokens — readable but clearly scrubbed
_REPLACEMENTS = {
    "email":          "[EMAIL]",
    "phone_us":       "[PHONE]",
    "phone_intl":     "[PHONE]",
    "ssn":            "[SSN]",
    "credit_card":    "[CC]",
    "ip_address":     "[IP]",
    "date_of_birth":  "[DOB]",
    "mrn":            "[MRN]",
    "url_with_token": "[URL]",
    "health_plan_id": "[HEALTH_ID]",
    "npi":            "[NPI]",
    "dea_number":     "[DEA]",
    # spaCy NER types
    "PERSON":         "[NAME]",
    "GPE":            "[LOCATION]",   # Geo-political entity
    "LOC":            "[LOCATION]",
    "FAC":            "[LOCATION]",   # Facility (hospitals, clinics)
    "ORG":            "[ORG]",
}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class PIIScanResult:
    pii_detected:      bool
    phi_detected:      bool
    redacted_text:     Optional[str]   # None if nothing was redacted
    findings:          list[str]       # human-readable list of what was found


# ---------------------------------------------------------------------------
# Core scanner
# ---------------------------------------------------------------------------

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
                pii_found = True  # PHI is always PII

        # ------------------------------------------------------------------
        # Pass 2 — spaCy NER (unstructured PII: names, locations)
        # ------------------------------------------------------------------
        try:
            nlp = _get_nlp()
            doc = nlp(redacted)   # run on already-regex-redacted text
            ner_replacements = []

            for ent in doc.ents:
                if ent.label_ in ("PERSON", "GPE", "LOC", "FAC"):
                    ner_replacements.append((ent.text, ent.label_))

            # Apply NER replacements (longest match first to avoid partial overlaps)
            ner_replacements.sort(key=lambda x: len(x[0]), reverse=True)
            for ent_text, ent_label in ner_replacements:
                token = _REPLACEMENTS.get(ent_label, "[ENTITY]")
                # Only replace if it looks like a real name/place (>2 chars, not
                # already a redaction token)
                if len(ent_text) > 2 and not ent_text.startswith("["):
                    redacted = redacted.replace(ent_text, token)
                    findings.append(f"spacy:{ent_label}:{ent_text[:20]}")
                    pii_found = True

        except Exception as e:
            # spaCy failure is non-fatal — regex pass is still valid
            logger.warning(f"spaCy NER pass failed (non-fatal): {e}")

        # ------------------------------------------------------------------
        # Return result
        # ------------------------------------------------------------------
        return PIIScanResult(
            pii_detected=pii_found,
            phi_detected=phi_found,
            redacted_text=redacted if pii_found else None,
            findings=findings,
        )


# ---------------------------------------------------------------------------
# Module-level singleton (used by PipelineProcessor)
# ---------------------------------------------------------------------------

_scanner_instance: Optional[PIIScanner] = None


        genome.pii_detected      = pii_found
        genome.phi_detected      = phi_found
        genome.pii_redacted_text = redacted if (pii_found or phi_found) else ""
        return genome
