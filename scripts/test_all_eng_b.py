"""
scripts/test_all.py — Full integration test for Engineer B's layer

Run with: python scripts/test_all.py
Expected: all tests pass with ✅
"""

import sys
import json
sys.path.insert(0, "backend")


# ------------------------------------------------------------------
# Test 1 — PII Scanner
# ------------------------------------------------------------------
def test_pii_scanner():
    from pipeline.pii_scanner import get_scanner
    scanner = get_scanner()

    result = scanner.scan(
        "Hi, I'm John from Mumbai. Call me at +91-9876543210 "
        "or email john.doe@gmail.com. My SSN is 123-45-6789."
    )
    assert result.pii_detected,                "Should detect PII"
    assert result.phi_detected is False,       "No PHI in this text"
    assert "[EMAIL]"   in result.redacted_text, "Email should be redacted"
    assert "[PHONE]"   in result.redacted_text, "Phone should be redacted"
    assert "[SSN]"     in result.redacted_text, "SSN should be redacted"
    assert "[NAME]"    in result.redacted_text, "Name should be redacted"
    print("✅ PIIScanner: all assertions passed")


# ------------------------------------------------------------------
# Test 2 — Relevance filter
# ------------------------------------------------------------------
def test_relevance():
    from pipeline.relevance import is_relevant
    assert is_relevant(
        "I've been on Ozempic for 3 months and losing hair badly"
    ), "Should be relevant"
    assert not is_relevant("bitcoin to the moon buy now!!!"), "Should be spam"
    assert not is_relevant("ok"),                             "Too short"
    print("✅ Relevance: all assertions passed")


# ------------------------------------------------------------------
# Test 3 — NER Extractor
# ------------------------------------------------------------------
def test_ner():
    from pipeline.ner import get_ner_extractor
    ner    = get_ner_extractor()
    result = ner.extract(
        "I started Ozempic for type 2 diabetes and now have severe hair loss. "
        "My doctor at Mumbai General Hospital confirmed it."
    )
    assert "ozempic" in result.drugs,      f"Ozempic not found, got: {result.drugs}"
    assert any("hair" in s for s in result.symptoms), f"Hair loss not found, got: {result.symptoms}"
    assert any("diabetes" in c for c in result.conditions), f"Diabetes not found, got: {result.conditions}"
    print(f"✅ NER: drugs={result.drugs}, symptoms={result.symptoms[:2]}, rxnorm={result.rxnorm_map}")


# ------------------------------------------------------------------
# Test 4 — Classifier
# ------------------------------------------------------------------
def test_classifier():
    from pipeline.classifier import get_classifier
    clf = get_classifier()

    adr = clf.classify(
        "Ozempic caused severe hair loss — this side effect isn't on the label!"
    )
    assert adr.signal_type == "adverse_drug_reaction", f"Expected ADR, got: {adr.signal_type}"
    assert adr.confidence_score > 0.6

    mis = clf.classify(
        "Big pharma is hiding the fact that Ozempic cures cancer. Don't trust doctors."
    )
    assert mis.signal_type == "misinformation", f"Expected misinfo, got: {mis.signal_type}"

    print(f"✅ Classifier: ADR confidence={adr.confidence_score:.2f}, misinfo={mis.signal_type}")


# ------------------------------------------------------------------
# Test 5 — Scorer (FDA API)
# ------------------------------------------------------------------
def test_scorer():
    from pipeline.scorer import get_scorer
    scorer = get_scorer()

    result = scorer.score(
        text="I've been losing so much hair since starting Ozempic.",
        drugs=["ozempic"],
        symptoms=["hair loss"],
    )
    # Novelty should be high — hair loss not well documented for Ozempic
    assert result.novelty["score"] > 0.5,    f"Expected high novelty, got {result.novelty['score']}"
    assert isinstance(result.sentiment_score, float)
    assert 0.0 <= result.distress_level <= 1.0
    print(
        f"✅ Scorer: sentiment={result.sentiment_score:+.2f}, "
        f"distress={result.distress_level:.2f}, "
        f"novelty={result.novelty['score']:.2f}, "
        f"in_fda_label={result.novelty['in_fda_label']}, "
        f"faers_count={result.novelty['faers_count']}"
    )


# ------------------------------------------------------------------
# Test 6 — Full Pipeline (Scenario 1: Ozempic hair loss)
# ------------------------------------------------------------------
def test_full_pipeline_scenario1():
    from pipeline.processor import PipelineProcessor

    post = {
        "post_id":     "scenario1-001",
        "source":      "reddit/r/diabetes",
        "source_type": "reddit",
        "text": (
            "I've been on Ozempic for 3 months. John from Mumbai warned me, "
            "and now I'm losing so much hair. My email is test@example.com. "
            "This is NOT mentioned on the label anywhere. "
            "Has anyone else had hair loss on Ozempic?"
        ),
        "url":       "https://reddit.com/r/diabetes/scenario1",
        "author":    "u/testuser",
        "timestamp": "2026-05-05T10:00:00Z",
        "metadata":  {"subreddit": "diabetes", "score": 42, "geo_proxy": "IN"},
    }

    processor = PipelineProcessor()
    genome    = processor.process(post)

    assert genome is not None,                              "Pipeline should not filter this post"
    assert genome["signal_type"] == "adverse_drug_reaction", f"Wrong type: {genome['signal_type']}"
    assert "ozempic" in genome["entities"]["drugs"],        "Ozempic not in entities"
    assert genome["pii_detected"] is True,                  "PII should be detected"
    assert genome["novelty"]["score"] > 0.5,                "Novelty should be high"
    assert len(genome["explanation"]) > 50,                 "Explanation should be generated"

    print("\n✅ FULL PIPELINE — Scenario 1 (Ozempic hair loss)")
    print(f"   Signal type:   {genome['signal_type']}")
    print(f"   Drugs:         {genome['entities']['drugs']}")
    print(f"   Symptoms:      {genome['entities']['symptoms']}")
    print(f"   Novelty score: {genome['novelty']['score']:.2f}")
    print(f"   In FDA label:  {genome['novelty']['in_fda_label']}")
    print(f"   FAERS count:   {genome['novelty']['faers_count']}")
    print(f"   PII detected:  {genome['pii_detected']}")
    print(f"   Explanation:   {genome['explanation'][:120]}...")


# ------------------------------------------------------------------
# Test 7 — Scenario 2: Contaminated cough syrup (outbreak)
# ------------------------------------------------------------------
def test_full_pipeline_scenario2():
    from pipeline.processor import PipelineProcessor

    processor = PipelineProcessor()
    platforms = [
        ("reddit",  "reddit/r/parenting"),
        ("twitter", "twitter"),
        ("forum",   "patient.info/forum"),
    ]

    genomes = []
    for i in range(12):  # 12 posts to trigger VOLUME condition
        source_type, source = platforms[i % len(platforms)]
        post = {
            "post_id":     f"scenario2-{i:03d}",
            "source":      source,
            "source_type": source_type,
            "text": (
                f"My child had respiratory failure after taking Doc-1 Max cough syrup. "
                f"This is serious — we ended up in the ER. Post #{i}."
            ),
            "url":       f"https://example.com/post/{i}",
            "author":    f"user_{i}",
            "timestamp": "2026-05-05T10:00:00Z",
            "metadata":  {},
        }
        genome = processor.process(post)
        if genome:
            genomes.append(genome)

    assert len(genomes) >= 10, f"Expected ≥10 genomes, got {len(genomes)}"
    print(f"\n✅ FULL PIPELINE — Scenario 2 (Contaminated cough syrup)")
    print(f"   Processed {len(genomes)} posts")
    print(f"   Signal types: {set(g['signal_type'] for g in genomes)}")
    print(f"   Novelty scores: {[round(g['novelty']['score'], 2) for g in genomes[:3]]}")
    print(f"   (Check logs above for 🚨 OUTBREAK ALERT)")


# ------------------------------------------------------------------
# Run all
# ------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("Patient Safety Sentinel — Engineer B Test Suite")
    print("=" * 60)

    tests = [
        test_pii_scanner,
        test_relevance,
        test_ner,
        test_classifier,
        test_scorer,
        test_full_pipeline_scenario1,
        test_full_pipeline_scenario2,
    ]

    for test in tests:
        try:
            test()
        except AssertionError as e:
            print(f"❌ FAILED: {test.__name__}: {e}")
        except Exception as e:
            print(f"💥 ERROR in {test.__name__}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("Test suite complete.")