"""
scripts/test_pipeline.py - Smoke test for the full pipeline
Run to verify the system works end to end before demo.
Usage: python scripts/test_pipeline.py
"""
import sys
sys.path.append("./backend")

from pipeline.processor import PipelineProcessor

TEST_POST = {
    "post_id":     "test-001",
    "source":      "reddit/r/diabetes",
    "source_type": "reddit",
    "url":         "https://reddit.com/test",
    "text":        "I have been on Ozempic for 3 weeks and my hair is falling out badly. "
                   "Also feeling very dizzy. My name is John and I live in Mumbai. "
                   "Has anyone else experienced this side effect?",
    "author":      "test_user",
    "timestamp":   "2024-01-01T00:00:00",
    "metadata":    {"subreddit": "diabetes", "geo_proxy": "IN-MH"},
}

def test():
    print("Initialising pipeline...")
    processor = PipelineProcessor()
    print("Processing test post...")
    genome = processor.process(TEST_POST)
    if genome:
        print("\n✅ Pipeline SUCCESS")
        print(f"  Genome ID:     {genome.genome_id}")
        print(f"  Signal type:   {genome.signal_type}")
        print(f"  Drugs:         {genome.entities.drugs}")
        print(f"  Symptoms:      {genome.entities.symptoms}")
        print(f"  Locations:     {genome.entities.locations}")
        print(f"  Sentiment:     {genome.sentiment_score:.2f}")
        print(f"  Novelty:       {genome.novelty.score:.2f}")
        print(f"  PII detected:  {genome.pii_detected}")
        print(f"  Explanation:   {genome.explanation}")
    else:
        print("❌ Pipeline returned None — post was filtered as irrelevant")

if __name__ == "__main__":
    test()
