"""
processor.py — PipelineProcessor

Orchestrates all 6 pipeline steps for a single RawPost → SignalGenome.

Step 1: PIIScanner    — redact before anything else touches the data
Step 2: Relevance     — drop noise early (saves model compute)
Step 3: NERExtractor  — extract drugs, symptoms, conditions, locations
Step 4: Classifier    — signal_type + confidence
Step 5: Scorer        — sentiment, distress, novelty (FDA cross-ref)
Step 6: XAI explain   — human-readable explanation

Output is stored in ChromaDB, then checked by OutbreakDetector.
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from pipeline.pii_scanner   import get_scanner
from pipeline.relevance      import is_relevant          # scaffold — keep as is
from pipeline.ner            import get_ner_extractor
from pipeline.classifier     import get_classifier        # scaffold lazy-fixed
from pipeline.scorer         import get_scorer
from storage.chroma_store    import get_chroma_store
from analysis.outbreak_detector import get_outbreak_detector

logger = logging.getLogger(__name__)


class PipelineProcessor:
    """
    Main entry point for Engineer B's layer.
    Call .process(raw_post_dict) → SignalGenome dict

    Engineer A drops RawPost dicts into the queue.
    Engineer C reads SignalGenome dicts from the API.
    """

    def __init__(self):
        # All components are singletons with lazy internals
        self.scanner   = get_scanner()
        self.ner       = get_ner_extractor()
        self.classifier = get_classifier()
        self.scorer    = get_scorer()
        self.store     = get_chroma_store()
        self.detector  = get_outbreak_detector()

    def process(self, raw_post: dict) -> Optional[dict]:
        """
        Process one RawPost. Returns SignalGenome dict, or None if filtered.
        """
        post_id = raw_post.get("post_id", str(uuid.uuid4()))
        text    = raw_post.get("text", "")
        logger.info(f"Processing post {post_id[:8]}…")

        # ------------------------------------------------------------------
        # Step 1 — PII Scan (MUST be first — redact before any model sees data)
        # ------------------------------------------------------------------
        scan = self.scanner.scan(text)
        safe_text = scan.redacted_text if scan.pii_detected else text

        # ------------------------------------------------------------------
        # Step 2 — Relevance filter (drop noise early)
        # ------------------------------------------------------------------
        if not is_relevant(safe_text):
            logger.debug(f"Post {post_id[:8]} filtered as irrelevant.")
            return None

        # ------------------------------------------------------------------
        # Step 3 — NER: extract entities from safe text
        # ------------------------------------------------------------------
        ner_result = self.ner.extract(safe_text)

        # ------------------------------------------------------------------
        # Step 4 — Classification: signal_type
        # ------------------------------------------------------------------
        classification = self.classifier.classify(safe_text, ner_result)

        # ------------------------------------------------------------------
        # Step 5 — Scoring: sentiment + distress + novelty (FDA API)
        # ------------------------------------------------------------------
        score_result = self.scorer.score(
            text=safe_text,
            drugs=ner_result.drugs,
            symptoms=ner_result.symptoms,
        )

        # ------------------------------------------------------------------
        # Step 6 — XAI explanation
        # ------------------------------------------------------------------
        explanation = self._build_explanation(
            raw_post, ner_result, classification, score_result, scan
        )

        # ------------------------------------------------------------------
        # Assemble SignalGenome (matches locked genome.py schema exactly)
        # ------------------------------------------------------------------
        genome_id  = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        metadata   = raw_post.get("metadata", {})

        genome = {
            "genome_id":        genome_id,
            "post_id":          post_id,
            "created_at":       created_at,
            "source":           raw_post.get("source", ""),
            "source_type":      raw_post.get("source_type", ""),
            "source_url":       raw_post.get("url", ""),
            "raw_text":         text,          # original (not redacted)
            "signal_type":      classification.signal_type,
            "sentiment_score":  score_result.sentiment_score,
            "distress_level":   score_result.distress_level,
            "confidence_score": score_result.confidence_score,
            "entities": {
                "drugs":        ner_result.drugs,
                "symptoms":     ner_result.symptoms,
                "conditions":   ner_result.conditions,
                "locations":    ner_result.locations,
                "institutions": ner_result.institutions,
            },
            "geo": {
                "extracted_locations":  ner_result.locations,
                "subreddit_geo_proxy":  metadata.get("geo_proxy", ""),
                "google_trends_region": "",   # filled by TrendAnalyzer
                "confidence":           0.5,
            },
            "novelty": score_result.novelty,
            "pii_detected":      scan.pii_detected,
            "phi_detected":      scan.phi_detected,
            "pii_redacted_text": scan.redacted_text,
            "explanation":       explanation,
            "cluster_id":        None,         # filled by ChromaDB clustering
            "related_genome_ids": [],          # filled below
        }

        # ------------------------------------------------------------------
        # Store in ChromaDB + find related genomes
        # ------------------------------------------------------------------
        try:
            # Find similar BEFORE storing (so we don't match self)
            similar = self.store.find_similar(safe_text, n_results=5)
            genome["related_genome_ids"] = [
                s["genome_id"] for s in similar
                if s.get("genome_id") != genome_id
            ]

            # Assign cluster_id from most similar genome if close enough
            if similar and similar[0]["similarity"] > 0.85:
                genome["cluster_id"] = similar[0].get("cluster_id") or genome_id

            self.store.store_genome(genome)
        except Exception as e:
            logger.error(f"ChromaDB store failed (non-fatal): {e}")

        # ------------------------------------------------------------------
        # Outbreak detection
        # ------------------------------------------------------------------
        try:
            if ner_result.drugs and ner_result.symptoms:
                alert = self.detector.check(
                    ner_result.drugs[0],
                    ner_result.symptoms[0],
                )
                if alert:
                    # Engineer C will consume this via the alerts queue/WebSocket
                    logger.warning(f"Outbreak alert: {alert.severity} — {alert.summary}")
                    # TODO: push alert to Engineer C's alert queue here
        except Exception as e:
            logger.error(f"Outbreak detection failed (non-fatal): {e}")

        logger.info(
            f"✅ Genome {genome_id[:8]} | "
            f"type={genome['signal_type']} | "
            f"novelty={genome['novelty']['score']:.2f} | "
            f"drugs={ner_result.drugs[:2]}"
        )
        return genome

    # ------------------------------------------------------------------
    # XAI explanation builder (Step 6)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_explanation(
        raw_post, ner_result, classification, score_result, scan
    ) -> str:
        drugs    = ", ".join(ner_result.drugs[:3])    or "none detected"
        symptoms = ", ".join(ner_result.symptoms[:3]) or "none detected"
        novelty  = score_result.novelty.get("score", 0.0)
        in_label = score_result.novelty.get("in_fda_label", False)
        faers    = score_result.novelty.get("faers_count", 0)
        source   = raw_post.get("source", "unknown source")

        novelty_explain = (
            f"This symptom is NOT documented in the FDA label for {drugs} "
            f"and has only {faers} FAERS reports — novelty score {novelty:.2f}."
            if not in_label else
            f"This symptom IS documented in the FDA label for {drugs} "
            f"({faers} FAERS reports) — novelty score {novelty:.2f}."
        )

        pii_note = (
            " ⚠️ PII/PHI detected and redacted before analysis."
            if scan.pii_detected else ""
        )

        sentiment_word = (
            "negative" if score_result.sentiment_score < -0.2
            else "positive" if score_result.sentiment_score > 0.2
            else "neutral"
        )

        return (
            f"Post from {source} classified as "
            f"'{classification.signal_type}' "
            f"(confidence {score_result.confidence_score:.0%}). "
            f"Detected drugs: {drugs}. "
            f"Detected symptoms: {symptoms}. "
            f"Sentiment: {sentiment_word} ({score_result.sentiment_score:+.2f}). "
            f"Distress level: {score_result.distress_level:.2f}. "
            f"{novelty_explain}"
            f"{pii_note}"
        )


# Standalone function for worker import
def process_post(raw_post: dict) -> Optional[dict]:
    """
    Process a single raw post through the pipeline.
    Returns SignalGenome dict or None if filtered.
    """
    processor = PipelineProcessor()
    return processor.process(raw_post)