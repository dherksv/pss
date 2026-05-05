"""
pii_scanner.py — Step 1 of PipelineProcessor

Scans raw post text for PII (Personally Identifiable Information) and
PHI (Protected Health Information) before any other processing touches the data.

Two-pass approach:
  Pass 1 — Regex: catches structured PII (emails, phones, SSNs, IPs, dates-of-birth)
  Pass 2 — spaCy NER: catches unstructured PII (person names, specific locations)

CRITICAL: spaCy model is lazy-loaded — never at import time.
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy model loader — fixes the Docker startup crash
# ---------------------------------------------------------------------------

_nlp = None  # module-level singleton, never loaded at import time


def _get_nlp():
    """
    Load spaCy model on first call only.
    Uses the pre-installed wheel (en_core_web_sm-3.7.1).
    Never call spacy.load() at module level — it crashes the worker
    before Docker has finished setting up the models layer.
    """
    global _nlp
    if _nlp is None:
        import spacy  # import also deferred — keeps module import fast
        logger.info("Loading spaCy model en_core_web_sm (first call)...")
        try:
            _nlp = spacy.load("en_core_web_sm")
            logger.info("spaCy model loaded successfully.")
        except OSError as e:
            logger.error(
                "spaCy model not found. Install with:\n"
                "pip install https://github.com/explosion/spacy-models/releases/"
                "download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl"
                " --no-deps"
            )
            raise RuntimeError("spaCy en_core_web_sm not available") from e
    return _nlp


# ---------------------------------------------------------------------------
# Regex patterns — structured PII
# ---------------------------------------------------------------------------

_PII_PATTERNS = {
    # Contact info
    "email":         re.compile(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
    ),
    "phone_us":      re.compile(
        r"\b(?:\+?1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}\b"
    ),
    "phone_intl":    re.compile(
        r"\+\d{1,3}[\s\-]?\d{6,14}\b"
    ),

    # Identity numbers
    "ssn":           re.compile(
        r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"
    ),
    "credit_card":   re.compile(
        r"\b(?:\d{4}[\s\-]?){3}\d{4}\b"
    ),

    # Network
    "ip_address":    re.compile(
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
    ),

    # Dates that could be DOB (very specific formats)
    "date_of_birth": re.compile(
        r"\b(?:dob|date of birth|born|birthday)[:\s]+\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b",
        re.IGNORECASE
    ),

    # Medical record / patient ID patterns
    "mrn":           re.compile(
        r"\b(?:mrn|patient\s*id|record\s*#?)[:\s]*[A-Z0-9]{6,12}\b",
        re.IGNORECASE
    ),

    # URLs with potential user tokens
    "url_with_token": re.compile(
        r"https?://\S+(?:token|key|auth|session)=\S+",
        re.IGNORECASE
    ),
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

class PIIScanner:
    """
    Stateless scanner. Instantiate once at startup (or use module-level
    singleton below). The spaCy model is loaded on first .scan() call.
    """

    def scan(self, text: str) -> PIIScanResult:
        """
        Full two-pass PII/PHI scan.

        Returns a PIIScanResult. If nothing is found, redacted_text is None
        (saves memory — downstream can use raw_text directly).
        """
        if not text or not text.strip():
            return PIIScanResult(False, False, None, [])

        findings: list[str] = []
        redacted = text
        pii_found = False
        phi_found = False

        # ------------------------------------------------------------------
        # Pass 1 — Regex scan (structured PII)
        # ------------------------------------------------------------------
        for label, pattern in _PII_PATTERNS.items():
            if pattern.search(redacted):
                replacement = _REPLACEMENTS.get(label, f"[{label.upper()}]")
                redacted = pattern.sub(replacement, redacted)
                findings.append(label)
                pii_found = True

        for label, pattern in _PHI_PATTERNS.items():
            if pattern.search(redacted):
                replacement = _REPLACEMENTS.get(label, f"[{label.upper()}]")
                redacted = pattern.sub(replacement, redacted)
                findings.append(label)
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


def get_scanner() -> PIIScanner:
    """Return the module-level PIIScanner singleton."""
    global _scanner_instance
    if _scanner_instance is None:
        _scanner_instance = PIIScanner()
    return _scanner_instance