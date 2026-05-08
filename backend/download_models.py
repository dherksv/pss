#!/usr/bin/env python3
"""
scripts/download_models.py
Downloads all NLP models to backend/models_cache/ before Docker build.
Run once: python scripts/download_models.py
"""
import os
import sys

# Allow model downloads during this script
if 'TRANSFORMERS_OFFLINE' in os.environ:
    del os.environ['TRANSFORMERS_OFFLINE']
if 'HF_HUB_OFFLINE' in os.environ:
    del os.environ['HF_HUB_OFFLINE']

os.environ['HF_HOME'] = '/app/models_cache/hub'
os.environ['TRANSFORMERS_CACHE'] = '/app/models_cache/hub'

cache_dir = '/app/models_cache/hub'
os.makedirs(cache_dir, exist_ok=True)

print("=" * 60)
print("Pre-caching models for offline operation...")
print("=" * 60)


print(f"Downloading models to: {CACHE_DIR}")
print("This will take 10–20 minutes and use ~1.5GB of disk space.\n")

from transformers import pipeline

# Model 1 — Biomedical NER
print("1/3 Downloading biomedical NER model (d4data/biomedical-ner-all)...")
try:
    pipeline("token-classification",
             model="d4data/biomedical-ner-all",
             aggregation_strategy="simple")
    print("    ✓ Biomedical NER ready\n")
except Exception as e:
    print(f"    ✗ Failed: {e}\n")
    sys.exit(1)

# Model 2 — Sentiment analysis
print("2/3 Downloading sentiment model (cardiffnlp/twitter-roberta-base-sentiment-latest)...")
try:
    pipeline("sentiment-analysis",
             model="cardiffnlp/twitter-roberta-base-sentiment-latest")
    print("    ✓ Sentiment model ready\n")
except Exception as e:
    print(f"    ✗ Failed: {e}\n")
    sys.exit(1)

# Model 3 — Emotion / distress classification
print("3/3 Downloading emotion model (j-hartmann/emotion-english-distilroberta-base)...")
try:
    pipeline("text-classification",
             model="j-hartmann/emotion-english-distilroberta-base",
             return_all_scores=True)
    print("    ✓ Emotion model ready\n")
except Exception as e:
    print(f"    ✗ Failed: {e}\n")
    sys.exit(1)

# Download sentence-transformers model
print("\n[1/2] sentence-transformers/all-MiniLM-L6-v2...")
try:
    from sentence_transformers import SentenceTransformer
    SentenceTransformer(
        "all-MiniLM-L6-v2",
        cache_folder=cache_dir,
    )
    print("✓ Cached successfully")
except Exception as e:
    print(f"✗ Failed: {e}")
    # Non-fatal — will retry at runtime if needed    

print("=" * 50)
print("All models downloaded successfully.")
print(f"Location: {CACHE_DIR}")
print("\nYou can now run: docker compose up --build")
print("=" * 50)
