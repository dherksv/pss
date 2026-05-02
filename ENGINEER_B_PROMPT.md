# Engineer B — NLP Pipeline, Analysis Engine & Agents

## Your Role
You own the intelligence layer. Raw social posts come in from Engineer A's
crawlers. You transform them into structured Signal Genomes using NLP models,
cross-reference against FDA APIs, detect outbreak patterns, and generate
explainable AI summaries. This is the scientific core of the product.

## What We Are Building
Patient Safety Sentinel — a real-time social listening system for healthcare.
Your pipeline converts raw posts into Signal Genomes — rich structured objects
with entity extraction, sentiment/distress/novelty scores, FDA cross-reference,
and a human-readable explanation. The Outbreak Detector watches genomes for
dangerous patterns and fires alerts.

## System Architecture (Your Layers)
```
[Queue — Engineer A fills this]
        ↓
[PipelineProcessor — YOU build this — 6 steps]
  Step 1: PIIScanner    — scan + redact before anything else
  Step 2: Relevance     — filter noise early
  Step 3: NERExtractor  — BioBERT + spaCy + RxNorm
  Step 4: Classifier    — ADR / distress / misinfo / dissatisfaction
  Step 5: Scorer        — sentiment + novelty + FDA cross-reference
  Step 6: XAI explain   — human readable explanation per genome
        ↓
[ChromaDB vector store — YOU build this]
        ↓
[OutbreakDetector — YOU build this]
[TrendAnalyzer — YOU build this]
[SourceDiscoveryAgent — YOU build this — AGENTIC BONUS]
        ↓
[FastAPI routes — Engineer C serves your output]
```

## Your Files to Implement
```
backend/pipeline/processor.py     ✅ scaffold done — wire all steps
backend/pipeline/pii_scanner.py   ✅ scaffold done — test + harden
backend/pipeline/relevance.py     ✅ scaffold done — upgrade if time
backend/pipeline/ner.py           🔧 implement BioBERT + RxNorm calls
backend/pipeline/classifier.py    ✅ scaffold done — test classification
backend/pipeline/scorer.py        🔧 implement FDA API calls for novelty
backend/storage/chroma_store.py   🔧 implement store + similarity query
backend/analysis/outbreak_detector.py 🔧 implement 3 trigger conditions
backend/analysis/trend_analyzer.py    ✅ scaffold done — test pytrends
backend/agents/source_discovery.py   ✅ scaffold done — extend if time
backend/models/genome.py          ✅ locked — DO NOT change field names
```

## Models to Use (All Free, Run Locally)
```python
# NER — biomedical entities
from transformers import pipeline
bio_ner = pipeline("ner", model="allenai/scibert_scivocab_uncased",
                   aggregation_strategy="simple")

# Sentiment
sentiment = pipeline("sentiment-analysis",
                     model="cardiffnlp/twitter-roberta-base-sentiment-latest")

# Distress / mental health
distress = pipeline("text-classification",
                    model="mental/mental-roberta-base")
```
Load all three ONCE at module level. Never reload per request.

## Free External APIs (No Key Needed)
```python
# FDA Drug Label — is symptom documented?
https://api.fda.gov/drug/label.json
?search=openfda.brand_name:"ozempic"&limit=1

# FDA FAERS — how many adverse event reports?
https://api.fda.gov/drug/event.json
?search=patient.drug.medicinalproduct:"ozempic"+AND+patient.reaction.reactionmeddrapt:"hair loss"&limit=1

# RxNorm — normalize drug name
https://rxnav.nlm.nih.gov/REST/rxcui.json?name=ozempic
```

## The Novelty Score Formula
```
novelty_score = label_factor + faers_factor
label_factor  = 0.0 if symptom in FDA label else 0.5
faers_factor  = max(0.0, 0.5 - (faers_count / 10000))
```
High novelty (>0.7) = potentially undocumented signal. This is your
headline demo moment.

## Outbreak Detection — 3 Trigger Conditions
```
Condition 1 — Volume:   >10 posts for same drug+symptom in 6 hours
Condition 2 — Novelty:  >3 high-novelty (>0.7) genomes for same pair
Condition 3 — Platform: same signal on 3+ different platforms
Severity: 1 trigger=watch, 2=warning, 3=alert
```

## How to Test
```bash
# Test full pipeline on one post
python scripts/test_pipeline.py

# Expected output:
# ✅ Pipeline SUCCESS
# Signal type: adverse_drug_reaction
# Drugs: ['Ozempic']
# Symptoms: ['hair loss']
# Novelty: 0.84
# PII detected: True (because test post mentions "John" and "Mumbai")
```

## How to Collaborate
- Work on branch: feature/nlp-pipeline, feature/outbreak-detector
- Merge to dev every evening
- genome.py schema is LOCKED. If you need new fields, ask both engineers.
- Your output (SignalGenome) is consumed by Engineer C's API routes.
- Your daily standup: "Pipeline processing? Scores sensible? Outbreak firing?"

## Demo Scenarios You Power
1. Ozempic hair loss — high novelty score, not in FDA label
2. Contaminated syrup — novelty=0.95, zero FAERS history, outbreak fires
   with severity=ALERT across r/Parenting + Twitter + forum
