"""
scripts/seed_data.py - Pre-seed demo data
Run before demo to populate ChromaDB + SQLite with realistic signal data.
Usage: python scripts/seed_data.py
"""
import sys, json, uuid, os

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_PATHS = [
    os.path.normpath(os.path.join(HERE, '..', 'backend')),
    os.path.normpath(os.path.join(HERE, '..')),
]
for path in BACKEND_PATHS:
    if os.path.isdir(path):
        sys.path.insert(0, path)
        break

from storage.sqlite_store import init_db, save_genome
from models.genome import SignalGenome, Entities, NoveltyScore

SEED_GENOMES = [
    # Ozempic scenario
    {
        "source": "reddit/r/ozempic", "source_type": "reddit",
        "signal_type": "adverse_drug_reaction",
        "drugs": ["Ozempic"], "symptoms": ["hair loss"],
        "sentiment_score": -0.82, "novelty_score": 0.84, "confidence_score": 0.91,
        "in_fda_label": False, "faers_count": 12,
        "explanation": "User reports unexpected hair loss after 3 weeks on Ozempic. Symptom not prominently documented in current FDA label. Novelty score elevated at 0.84.",
    },
    {
        "source": "reddit/r/diabetes", "source_type": "reddit",
        "signal_type": "adverse_drug_reaction",
        "drugs": ["Ozempic"], "symptoms": ["gastroparesis", "severe nausea"],
        "sentiment_score": -0.91, "novelty_score": 0.45, "confidence_score": 0.88,
        "in_fda_label": True, "faers_count": 3420,
        "explanation": "Severe gastroparesis reported. Symptom IS documented in FDA label. Historical FAERS count high — known side effect being rediscovered.",
    },
    # Contaminated syrup scenario
    {
        "source": "reddit/r/Parenting", "source_type": "reddit",
        "signal_type": "adverse_drug_reaction",
        "drugs": ["Doc-1 Max"], "symptoms": ["respiratory failure", "unconscious"],
        "sentiment_score": -0.98, "novelty_score": 0.95, "confidence_score": 0.94,
        "in_fda_label": False, "faers_count": 0,
        "explanation": "CRITICAL: Parent reports child became unconscious after cough syrup. Symptom-drug pair has ZERO historical FAERS reports. Novelty score: 0.95. Requires immediate review.",
    },
]

def seed():
    init_db()
    for data in SEED_GENOMES:
        g = SignalGenome(
            source         = data["source"],
            source_type    = data["source_type"],
            signal_type    = data["signal_type"],
            sentiment_score= data["sentiment_score"],
            confidence_score=data["confidence_score"],
            explanation    = data["explanation"],
        )
        g.entities = Entities(
            drugs=data["drugs"], symptoms=data["symptoms"])
        g.novelty = NoveltyScore(
            score=data["novelty_score"],
            in_fda_label=data["in_fda_label"],
            faers_count=data["faers_count"])
        save_genome(g, project_id="demo-project")
        print(f"Seeded genome: {g.genome_id} | {g.signal_type} | {g.entities.drugs}")
    print(f"\nSeeded {len(SEED_GENOMES)} genomes successfully.")

if __name__ == "__main__":
    seed()
