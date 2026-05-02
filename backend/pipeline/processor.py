"""
pipeline/processor.py - Main pipeline orchestrator | OWNER: Engineer B
Takes a RawPost dict, runs all pipeline steps, returns a SignalGenome.
Steps run in strict order - PII scan always first.
"""
import logging
from models.genome import SignalGenome, Entities, GeoSignal, NoveltyScore
from pipeline.pii_scanner import PIIScanner
from pipeline.relevance import RelevanceChecker
from pipeline.ner import NERExtractor
from pipeline.classifier import SignalClassifier
from pipeline.scorer import SignalScorer

log = logging.getLogger("pipeline")


class PipelineProcessor:
    def __init__(self):
        log.info("Initialising pipeline components...")
        self.pii_scanner  = PIIScanner()
        self.relevance    = RelevanceChecker()
        self.ner          = NERExtractor()
        self.classifier   = SignalClassifier()
        self.scorer       = SignalScorer()
        log.info("Pipeline ready.")

    def process(self, raw_post: dict) -> SignalGenome | None:
        """
        Full pipeline: RawPost -> SignalGenome
        Returns None if post is irrelevant or fails pipeline.
        """
        genome = SignalGenome(
            post_id        = raw_post["post_id"],
            source         = raw_post["source"],
            source_type    = raw_post["source_type"],
            source_url     = raw_post["url"],
            raw_text       = raw_post["text"],
            author         = raw_post.get("author", ""),
            post_timestamp = raw_post.get("timestamp", ""),
        )

        # Step 1 — PII/PHI scan (ALWAYS FIRST)
        genome = self.pii_scanner.scan(genome)

        # Use redacted text for all downstream processing
        working_text = genome.pii_redacted_text or genome.raw_text

        # Step 2 — Relevance check (discard noise early)
        if not self.relevance.is_relevant(working_text):
            log.debug(f"Post {genome.post_id} filtered as irrelevant")
            return None

        # Step 3 — Entity extraction
        entities, geo = self.ner.extract(working_text, raw_post.get("metadata", {}))
        genome.entities = entities
        genome.geo      = geo

        # Step 4 — Signal classification
        genome.signal_type = self.classifier.classify(working_text, entities)

        # Step 5 — Scoring (sentiment, distress, confidence, novelty)
        genome = self.scorer.score(genome, working_text)

        # Step 6 — XAI explanation generation
        genome.explanation = self._explain(genome)

        log.info(f"Genome {genome.genome_id} | type={genome.signal_type} | novelty={genome.novelty.score:.2f}")
        return genome

    def _explain(self, genome: SignalGenome) -> str:
        """Generate a human-readable explanation for why this genome was flagged."""
        drugs    = ", ".join(genome.entities.drugs) or "unknown drug"
        symptoms = ", ".join(genome.entities.symptoms) or "unspecified symptoms"
        parts = [
            f"Signal type: {genome.signal_type}.",
            f"Detected entities: {drugs} associated with {symptoms}.",
            f"Sentiment: {'negative' if genome.sentiment_score < -0.3 else 'neutral/positive'} "
            f"(score: {genome.sentiment_score:.2f}).",
            f"Confidence: {genome.confidence_score:.2f}.",
        ]
        if genome.novelty.score > 0.7:
            parts.append(
                f"HIGH NOVELTY ({genome.novelty.score:.2f}): "
                f"symptom not prominently found in FDA label or recent reports."
            )
        if genome.pii_detected:
            parts.append("PII/PHI detected and redacted before processing.")
        return " ".join(parts)
