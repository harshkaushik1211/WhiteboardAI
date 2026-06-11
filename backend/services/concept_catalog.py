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

# Educational Canonical Ontology (Component 3)
CANONICAL_CONCEPTS = {
    "physics": {
        "ball",
        "car",
        "force",
        "friction",
        "lightbulb",
        "magnet",
        "pulley",
        "rocket",
        "wave",
        "arrow-curved",
        "arrow-down",
        "arrow-left",
        "arrow-right",
        "arrow-up",
    },
    "biology": {
        "atp",
        "bacteria",
        "bloodstream",
        "brain",
        "cell",
        "chloroplast",
        "crossed-o2",
        "dna",
        "energy",
        "glucose",
        "heart",
        "leaf",
        "lungs",
        "mitochondria",
        "oxygen",
        "photosynthesis_diagram",
        "plant",
        "search-magnify-magnifier-glass",
        "sun",
        "human",
        "person",
    },
    "chemistry": {
        "atom",
        "co2",
        "ethanol",
        "flask",
        "molecule",
        "o2",
        "water",
    },
    "computer_science": {
        "client",
        "cloud",
        "database",
        "handshake",
        "laptop",
        "packet",
        "server",
    },
    "mathematics": {
        "array",
        "chart bar",
        "midpoint",
        "pointer",
        "sorted list",
    }
}

# Domain-aware vocabulary aliases (Component 3)
ONTOLOGY_ALIASES = {
    "physics": {
        "football": "ball",
        "soccer ball": "ball",
        "moving ball": "ball",
        "stationary ball": "ball",
        "reaction force": "force",
        "push force": "force",
        "pull force": "force",
        "gravitational force": "force",
        "tension": "force",
        "air escaping": "wave",
        "airflow": "wave",
        "truck": "car",
        "sedan": "car",
        "automobile": "car",
        "delivery truck": "car",
        "speed increase": "force",
        "accelerating": "force",
        "slowing down": "friction",
        "collision": "ball",
        "momentum": "ball",
        "seatbelt": "car",
        "velocity": "car",
        "acceleration": "force",
    },
    "biology": {
        "sunlight energy": "sun",
        "solar radiation": "sun",
        "light energy": "sun",
        "oxygen release": "oxygen",
        "o2 release": "oxygen",
        "carbon dioxide entering leaf": "co2",
        "carbon dioxide": "co2",
        "cell division": "cell",
        "mitosis": "cell",
        "meiosis": "cell",
        "plant cell": "cell",
        "stomata": "leaf",
        "rna": "dna",
        "nucleus": "cell",
        "glucose production": "glucose",
        "sugar": "glucose",
    },
    "chemistry": {
        "electron sharing": "atom",
        "covalent bond": "molecule",
        "ionic bond": "molecule",
        "electron": "atom",
        "acid solution": "flask",
        "acidic": "flask",
        "base solution": "flask",
        "basic": "flask",
        "neutralization reaction": "flask",
        "chemical reaction": "flask",
        "reaction": "flask",
        "water molecule": "water",
        "carbon dioxide": "co2",
        "oxygen": "o2",
    },
    "computer_science": {
        "middle element": "server",
        "array element": "server",
        "index": "server",
        "binary search": "server",
        "tree": "database",
        "internet": "cloud",
        "cpu": "server",
        "memory": "server",
    },
    "mathematics": {
        "middle element": "pointer",
        "array element": "pointer",
        "index": "pointer",
        "binary search": "array",
        "sorted list": "sorted list",
        "middle": "midpoint",
        "midpoint pointer": "pointer",
        "search pointer": "pointer",
        "left pointer": "pointer",
        "right pointer": "pointer",
        "line graph": "chart bar",
        "bar chart": "chart bar",
        "quadratic curve": "arrow-curved",
        "parabola": "arrow-curved",
        "vector arrow": "arrow-right",
        "circle": "midpoint",
        "triangle": "midpoint",
    }
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
