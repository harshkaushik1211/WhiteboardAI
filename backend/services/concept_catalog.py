"""Maps LLM concept names to canonical asset library concepts."""
import re

CONCEPT_ALIASES = {
    # Biology true synonyms
    "lung": "lungs",
    "human lungs": "lungs",
    "o2": "oxygen",
    "sugar": "glucose",
    "mitochondrion": "mitochondria",
    "plant cell": "plant",
    "tree": "plant",
    "photosynthesis": "photosynthesis_diagram",
    "photosynthesis diagram": "photosynthesis_diagram",
    "diagram": "photosynthesis_diagram",
    "chlorophyll": "leaf",
    "chloroplast": "chloroplast",
    "magnify": "magnify",
    "magnifying glass": "magnify",
    "magnifier": "magnify",
    "zoom": "magnify",
    "close-up": "magnify",
    "close up": "magnify",
    "light energy": "sun",
    "sunlight": "sun",
    "solar": "sun",
    
    # Chemistry true synonyms
    "carbon dioxide": "co2",
    "h2o": "water",
    "water molecule": "water",
    
    # Computer Science / Math true synonyms
    "sorted list": "sorted list",
    "mid point": "midpoint",
}

# Educational ontology mapping concept to its primary domain
CONCEPT_DOMAINS = {
    # Physics
    "force": "physics",
    "acceleration": "physics",
    "velocity": "physics",
    "friction": "physics",
    "momentum": "physics",
    "collision": "physics",
    "mass": "physics",
    "gravity": "physics",
    "car": "physics",
    "skateboard": "physics",
    "rocket": "physics",
    "seatbelt": "physics",
    "tug_of_war": "physics",
    "spring": "physics",
    "projectile": "physics",
    "ball": "physics",
    "magnet": "physics",
    "pulley": "physics",
    "wave": "physics",
    "lightbulb": "physics",

    # Biology
    "cell": "biology",
    "nucleus": "biology",
    "chloroplast": "biology",
    "stomata": "biology",
    "dna": "biology",
    "rna": "biology",
    "mitochondria": "biology",
    "photosynthesis": "biology",
    "leaf": "biology",
    "oxygen": "biology",
    "glucose": "biology",
    "lungs": "biology",
    "atp": "biology",
    "bloodstream": "biology",
    "heart": "biology",
    "plant": "biology",
    "bacteria": "biology",
    "brain": "biology",
    "human": "biology",

    # Chemistry
    "atom": "chemistry",
    "molecule": "chemistry",
    "reaction": "chemistry",
    "bond": "chemistry",
    "acid": "chemistry",
    "base": "chemistry",
    "electron": "chemistry",
    "compound": "chemistry",
    "co2": "chemistry",
    "water": "chemistry",
    "flask": "chemistry",
    "ethanol": "chemistry",
    "o2": "chemistry",

    # Computer Science / Math
    "binary_search": "computer_science",
    "array": "computer_science",
    "tree": "computer_science",
    "internet": "computer_science",
    "packet": "computer_science",
    "server": "computer_science",
    "cpu": "computer_science",
    "memory": "computer_science",
    "client": "computer_science",
    "cloud": "computer_science",
    "database": "computer_science",
    "handshake": "computer_science",
    "laptop": "computer_science",
    "sorted_list": "computer_science",
    "midpoint": "computer_science",
    "pointer": "computer_science"
}


def normalize_concept(concept: str) -> str:
    key = concept.lower().strip().replace("_", " ")
    if key in CONCEPT_ALIASES:
        return CONCEPT_ALIASES[key]
    for alias, canonical in CONCEPT_ALIASES.items():
        pattern = r"\b" + re.escape(alias) + r"\b"
        if re.search(pattern, key):
            return canonical
    return key


def available_concepts() -> list:
    from services.svg_indexer import get_index
    return sorted({e["concept"] for e in get_index()})
