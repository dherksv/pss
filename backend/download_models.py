#!/usr/bin/env python3
"""
Pre-download models for offline operation.
Run during Docker build to ensure models are cached before worker starts.
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

# Download transformers model
print("\n[2/2] mental/mental-roberta-base...")
try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    AutoTokenizer.from_pretrained(
        "mental/mental-roberta-base",
        cache_dir=cache_dir,
    )
    AutoModelForSequenceClassification.from_pretrained(
        "mental/mental-roberta-base",
        cache_dir=cache_dir,
    )
    print("✓ Cached successfully")
except Exception as e:
    print(f"✗ Failed: {e}")
    # Non-fatal — will retry at runtime if needed

print("\n" + "=" * 60)
print("Model pre-caching complete")
print("=" * 60)
