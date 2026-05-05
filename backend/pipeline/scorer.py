"""
pipeline/scorer.py - Scoring engine | OWNER: Engineer B
"""
import requests
from models.genome import SignalGenome, NoveltyScore

# Lazy reference
_sentiment_model = None

FDA_LABEL_URL = "https://api.fda.gov/drug/label.json"
FDA_FAERS_URL = "https://api.fda.gov/drug/event.json"

LABEL_MAP = {"positive": 1.0, "neutral": 0.0, "negative": -1.0}


def get_sentiment_model():
    global _sentiment_model
    if _sentiment_model is None:
        from transformers import pipeline as hf_pipeline
        print("Loading sentiment model...")
        _sentiment_model = hf_pipeline(
            "sentiment-analysis",
            model="cardiffnlp/twitter-roberta-base-sentiment-latest"
        )
        print("Sentiment model ready.")
    return _sentiment_model


class SignalScorer:
    def score(self, genome: SignalGenome, text: str) -> SignalGenome:
        genome = self._sentiment(genome, text)
        genome = self._novelty(genome)
        return genome

    def _sentiment(self, genome: SignalGenome, text: str) -> SignalGenome:
        try:
            result = get_sentiment_model()(text[:512])[0]
            label  = result["label"].lower()
            score  = result["score"]
            genome.sentiment_score  = LABEL_MAP.get(label, 0.0) * score
            genome.confidence_score = score
        except Exception as e:
            print(f"Sentiment error: {e}")
            genome.sentiment_score  = 0.0
            genome.confidence_score = 0.0
        return genome

    def _novelty(self, genome: SignalGenome) -> SignalGenome:
        """
        Cross-reference drug+symptom against:
        1. FDA drug label (is symptom documented?)
        2. FDA FAERS (how many historical reports?)
        Both APIs are free with no key required.
        """
        drugs    = genome.entities.drugs
        symptoms = genome.entities.symptoms

        if not drugs or not symptoms:
            genome.novelty = NoveltyScore(score=0.1)
            return genome

        drug    = drugs[0]
        symptom = symptoms[0]
        novelty = NoveltyScore()

        # Check FDA label
        try:
            resp = requests.get(FDA_LABEL_URL,
                params={"search": f'openfda.brand_name:"{drug}"', "limit": 1},
                timeout=8)
            label_text = str(resp.json()).lower()
            novelty.in_fda_label = symptom.lower() in label_text
        except Exception:
            novelty.in_fda_label = False

        # Check FAERS event count
        try:
            resp = requests.get(FDA_FAERS_URL,
                params={"search": f'patient.drug.medicinalproduct:"{drug}"'
                                  f'+AND+patient.reaction.reactionmeddrapt:"{symptom}"',
                        "limit": 1},
                timeout=8)
            novelty.faers_count = resp.json().get("meta", {}).get("results", {}).get("total", 0)
        except Exception:
            novelty.faers_count = 0

        # Compute final novelty score
        label_factor = 0.0 if novelty.in_fda_label else 0.5
        faers_factor = max(0.0, 0.5 - (novelty.faers_count / 10000))
        novelty.score = min(1.0, label_factor + faers_factor)
        genome.novelty = novelty
        return genome
