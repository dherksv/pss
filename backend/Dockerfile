FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip

RUN pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl
COPY requirements.txt .
RUN pip install --default-timeout=7000 --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

# Copy pre-downloaded models from your local machine into the image
COPY models_cache/ /app/models_cache/

# Copy model download helper script
COPY download_models.py /app/

# Pre-cache required models before enabling offline mode
# Models can be downloaded here; worker will run in offline mode
#RUN python /app/download_models.py || true

COPY . .

EXPOSE 8000