"""
chroma_store.py — Vector store for Signal Genomes

Uses ChromaDB (local, persistent) to:
  1. Store genome embeddings for similarity search
  2. Find related genomes (for cluster_id + related_genome_ids fields)
  3. Support OutbreakDetector time-window queries

Collection schema stored in metadata:
  - genome_id, post_id, drug, symptom, source_type, created_at, novelty_score
"""

import logging
import uuid
from typing import Optional
from datetime import datetime, timedelta, timezone

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ChromaDB client — lazy init
# ---------------------------------------------------------------------------

_client: Optional[chromadb.Client]    = None
_collection                            = None

CHROMA_PATH        = "./chroma_db"    # persisted to disk
COLLECTION_NAME    = "signal_genomes"


def _get_collection():
    global _client, _collection
    if _collection is None:
        logger.info("Initialising ChromaDB client...")
        _client = chromadb.PersistentClient(
            path=CHROMA_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},  # cosine similarity
        )
        logger.info(f"ChromaDB collection '{COLLECTION_NAME}' ready.")
    return _collection


# ---------------------------------------------------------------------------
# Embedding helper — use sentence-transformers (free, local)
# ---------------------------------------------------------------------------

_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading sentence-transformers model...")
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Sentence transformer loaded.")
    return _embedder


def _embed(text: str) -> list[float]:
    """Return embedding vector for text."""
    embedder = _get_embedder()
    return embedder.encode(text, normalize_embeddings=True).tolist()


# ---------------------------------------------------------------------------
# ChromaStore public API
# ---------------------------------------------------------------------------

class ChromaStore:

    def store_genome(self, genome) -> None:
        """
        Persist a SignalGenome into ChromaDB.
        genome: SignalGenome dataclass/dict (from models/genome.py)
        """
        col = _get_collection()

        # Text to embed: rich signal text
        embed_text = self._genome_to_embed_text(genome)
        embedding  = _embed(embed_text)

        # Flat metadata (ChromaDB only supports str/int/float/bool)
        drugs    = genome.entities.drugs    if hasattr(genome.entities, 'drugs')    else genome.get('entities', {}).get('drugs', [])
        symptoms = genome.entities.symptoms if hasattr(genome.entities, 'symptoms') else genome.get('entities', {}).get('symptoms', [])

        metadata = {
            "genome_id":     genome.genome_id    if hasattr(genome, 'genome_id')    else genome['genome_id'],
            "post_id":       genome.post_id       if hasattr(genome, 'post_id')       else genome['post_id'],
            "source_type":   genome.source_type   if hasattr(genome, 'source_type')   else genome['source_type'],
            "signal_type":   genome.signal_type   if hasattr(genome, 'signal_type')   else genome['signal_type'],
            "created_at":    genome.created_at    if hasattr(genome, 'created_at')    else genome['created_at'],
            "novelty_score": (genome.novelty.score if hasattr(genome, 'novelty') else genome.get('novelty', {}).get('score', 0.0)),
            "drug":          drugs[0]    if drugs    else "",
            "symptom":       symptoms[0] if symptoms else "",
        }

        col.upsert(
            ids=[metadata["genome_id"]],
            embeddings=[embedding],
            metadatas=[metadata],
            documents=[embed_text],
        )
        logger.debug(f"Stored genome {metadata['genome_id']} in ChromaDB.")

    def find_similar(
        self,
        text:          str,
        n_results:     int   = 5,
        min_similarity: float = 0.75,
    ) -> list[dict]:
        """
        Find genomes similar to the given text.
        Returns list of metadata dicts for matching genomes.
        """
        col       = _get_collection()
        embedding = _embed(text)

        try:
            results = col.query(
                query_embeddings=[embedding],
                n_results=min(n_results, col.count() or 1),
                include=["metadatas", "distances"],
            )
        except Exception as e:
            logger.warning(f"ChromaDB query failed: {e}")
            return []

        similar = []
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for meta, dist in zip(metadatas, distances):
            similarity = 1.0 - dist  # cosine: distance 0 = identical
            if similarity >= min_similarity:
                similar.append({**meta, "similarity": round(similarity, 4)})

        return similar

    def query_by_drug_symptom(
        self,
        drug:    str,
        symptom: str,
        hours:   int = 6,
    ) -> list[dict]:
        """
        Retrieve genomes matching drug+symptom within the last N hours.
        Used by OutbreakDetector for time-window analysis.
        """
        col = _get_collection()

        cutoff = (
            datetime.now(timezone.utc) - timedelta(hours=hours)
        ).isoformat()

        try:
            results = col.get(
                where={
                    "$and": [
                        {"drug":    {"$eq": drug.lower()}},
                        {"symptom": {"$eq": symptom.lower()}},
                        {"created_at": {"$gte": cutoff}},
                    ]
                },
                include=["metadatas"],
            )
            return results.get("metadatas", [])
        except Exception as e:
            logger.warning(f"ChromaDB drug/symptom query failed: {e}")
            return []

    def get_genome_count(self) -> int:
        return _get_collection().count()

    @staticmethod
    def _genome_to_embed_text(genome) -> str:
        """
        Construct rich text for embedding.
        Combines raw text + entities for better semantic search.
        """
        if hasattr(genome, 'raw_text'):
            raw   = genome.raw_text or ""
            drugs = " ".join(genome.entities.drugs)    if hasattr(genome.entities, 'drugs') else ""
            syms  = " ".join(genome.entities.symptoms) if hasattr(genome.entities, 'symptoms') else ""
        else:
            raw   = genome.get('raw_text', '')
            drugs = " ".join(genome.get('entities', {}).get('drugs', []))
            syms  = " ".join(genome.get('entities', {}).get('symptoms', []))

        return f"{raw} drugs: {drugs} symptoms: {syms}".strip()


# Module singleton
_store_instance: Optional[ChromaStore] = None


def get_chroma_store() -> ChromaStore:
    global _store_instance
    if _store_instance is None:
        _store_instance = ChromaStore()
    return _store_instance