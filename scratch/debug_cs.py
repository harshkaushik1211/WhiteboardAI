import sys
sys.path.append("c:/Users/harsh/OneDrive/Desktop/WhiteboardAI/backend")

from models.schemas import ConceptGraph, EducationalConcept, LessonPlan
from services.concept_decomposer import validate_concept_diversity, validate_coverage

def get_cs_graph() -> ConceptGraph:
    concepts = [
        EducationalConcept(concept_id="cpu", name="CPU", importance=0.95, visual_priority=0.90, concept_type="component"),
        EducationalConcept(concept_id="memory", name="Memory", importance=0.90, visual_priority=0.85, concept_type="component"),
        EducationalConcept(concept_id="process", name="Process", importance=0.90, visual_priority=0.75, concept_type="actor"),
        EducationalConcept(concept_id="scheduler", name="Scheduler", importance=0.85, visual_priority=0.70, concept_type="process", prerequisite_concepts=["cpu", "process"]),
        EducationalConcept(concept_id="thread", name="Thread", importance=0.80, visual_priority=0.70, concept_type="component", prerequisite_concepts=["process"]),
        EducationalConcept(concept_id="context_switch", name="Context Switch", importance=0.80, visual_priority=0.75, concept_type="process", prerequisite_concepts=["scheduler", "cpu"]),
        EducationalConcept(concept_id="queue", name="Queue", importance=0.70, visual_priority=0.80, concept_type="object"),
        EducationalConcept(concept_id="semaphore", name="Semaphore", importance=0.65, visual_priority=0.75, concept_type="state", prerequisite_concepts=["process"]),
    ]
    return ConceptGraph(topic="Operating Systems", domain="computer_science", concepts=concepts, edges=[])

# Let's import the simulate_allocate function from simulate_allocator
from simulate_allocator import simulate_allocate

lp = LessonPlan(concept_complexity="complex")
allocation = simulate_allocate(get_cs_graph(), lp, 6, 1.5, 3.0, True, "lower")
print("CS Allocation:")
for s, concepts in allocation.items():
    print(f"  Scene {s}: {concepts}")
diversity = validate_concept_diversity(allocation, 6)
print("CS Diversity metrics:")
for k, v in diversity.items():
    print(f"  {k}: {v}")
