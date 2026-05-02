FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download NLP models at build time (not at runtime)
RUN python -c "\
from transformers import pipeline; \
import os; \
os.environ['TRANSFORMERS_CACHE'] = '/app/models_cache'; \
print('Downloading BioBERT NER...'); \
pipeline('ner', model='allenai/scibert_scivocab_uncased', aggregation_strategy='simple'); \
print('Downloading Sentiment model...'); \
pipeline('sentiment-analysis', model='cardiffnlp/twitter-roberta-base-sentiment-latest'); \
print('Downloading Mental health model...'); \
pipeline('text-classification', model='mental/mental-roberta-base'); \
print('All models ready.')"

COPY . .

EXPOSE 8000
