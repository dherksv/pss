"""
storage/chroma_store.py - ChromaDB vector store | OWNER: Engineer B
Stores genome embeddings for:
- Similarity search (novelty scoring)
- Semantic clustering (outbreak detection)
- Related genome discovery
"""
import chromadb
from chromadb.utils import embedding_functions

client = chromadb.PersistentClient(path="/app/chroma_data")

embedder = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

collection = client.get_or_create_collection(
    name="signal_genomes",
    embedding_function=embedder,
    metadata={"hnsw:space": "cosine"},
)


def store_genome_vector(genome):
    """Store genome in ChromaDB for semantic search."""
    text = f"{genome.raw_text} {' '.join(genome.entities.drugs)} {' '.join(genome.entities.symptoms)}"
    collection.add(
        documents=[text],
        ids=[genome.genome_id],
        metadatas=[{
            "signal_type":    genome.signal_type,
            "novelty_score":  genome.novelty.score,
            "source_type":    genome.source_type,
            "drug":           genome.entities.drugs[0] if genome.entities.drugs else "",
            "symptom":        genome.entities.symptoms[0] if genome.entities.symptoms else "",
            "created_at":     genome.created_at,
        }]
    )


def find_similar_genomes(text: str, n: int = 10, filters: dict = None) -> list:
    """
    Find semantically similar genomes.
    Used by novelty scorer and outbreak detector.
    """
    where = filters or {}
    results = collection.query(
        query_texts=[text],
        n_results=n,
        where=where if where else None,
    )
    return results
