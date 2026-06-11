import sys
from pathlib import Path
sys.path.append('c:/Users/harsh/OneDrive/Desktop/WhiteboardAI/backend')

from models.schemas import ConceptGraph, EducationalConcept, ConceptRelationship, LessonPlan
from services.concept_decomposer import validate_concept_diversity, validate_coverage

# Define mock graphs
def get_physics_graph():
    concepts = [
        EducationalConcept(concept_id="force", name="Force", importance=0.95, visual_priority=0.90, concept_type="cause"),
        EducationalConcept(concept_id="mass", name="Mass", importance=0.85, visual_priority=0.80, concept_type="input"),
        EducationalConcept(concept_id="acceleration", name="Acceleration", importance=0.90, visual_priority=0.75, concept_type="effect", prerequisite_concepts=["force", "mass"]),
        EducationalConcept(concept_id="friction", name="Friction", importance=0.80, visual_priority=0.80, concept_type="process"),
        EducationalConcept(concept_id="gravity", name="Gravity", importance=0.80, visual_priority=0.85, concept_type="process"),
        EducationalConcept(concept_id="momentum", name="Momentum", importance=0.85, visual_priority=0.75, concept_type="process", prerequisite_concepts=["mass", "acceleration"]),
        EducationalConcept(concept_id="car", name="Car", importance=0.60, visual_priority=0.95, concept_type="actor"),
        EducationalConcept(concept_id="rocket", name="Rocket", importance=0.70, visual_priority=0.95, concept_type="actor"),
        EducationalConcept(concept_id="collision", name="Collision", importance=0.75, visual_priority=0.90, concept_type="effect", prerequisite_concepts=["momentum"]),
        EducationalConcept(concept_id="seatbelt", name="Seatbelt", importance=0.50, visual_priority=0.90, concept_type="component"),
    ]
    return ConceptGraph(topic="Newton's Laws", domain="physics", concepts=concepts, edges=[])

graph = get_physics_graph()
num_scenes = 6
concepts = graph.concepts
sorted_concept_ids = [c.concept_id for c in concepts]
concepts_by_id = {c.concept_id: c for c in concepts}

target_per_scene = 4
allocation = {s: [] for s in range(1, num_scenes + 1)}
concept_use_counts = {c.concept_id: 0 for c in concepts}

def get_max_reuse(importance):
    return 3 if importance > 0.8 else (2 if importance >= 0.5 else 1)

for s in range(1, num_scenes + 1):
    used_so_far = {cid for cid, count in concept_use_counts.items() if count > 0}
    remaining = len(concepts) - len(used_so_far)
    remaining_scenes = num_scenes - s + 1
    
    # Dynamic Limit Formula
    max_new_per_scene = max(1, remaining // remaining_scenes)
    if s == 1:
        max_new_per_scene = target_per_scene

    new_selected = 0
    for slot in range(target_per_scene):
        candidates = []
        for idx, cid in enumerate(sorted_concept_ids):
            c = concepts_by_id[cid]
            current_uses = concept_use_counts[cid]
            max_uses = get_max_reuse(c.importance)
            
            if current_uses >= max_uses or cid in allocation[s]:
                continue
                
            is_new = (cid not in used_so_far)
            
            new_penalty = 0.0
            if is_new and new_selected >= max_new_per_scene:
                new_penalty = 5.0
                
            ideal_scene = int(idx * num_scenes / len(sorted_concept_ids)) + 1
            progression_fit = 1.0 - abs(s - ideal_scene) / num_scenes
            
            coverage_need = 1.5 if current_uses == 0 else 0.0
            
            consec_penalty = 0.0
            if s > 1 and cid in allocation[s - 1]:
                consec_penalty = 2.0
                
            score = c.importance + c.visual_priority + coverage_need + 0.5 * progression_fit - consec_penalty - new_penalty
            candidates.append((score, cid))
            
        if not candidates:
            break
            
        candidates.sort(reverse=True, key=lambda x: x[0])
        best_cid = candidates[0][1]
        allocation[s].append(best_cid)
        if best_cid not in used_so_far:
            new_selected += 1
            used_so_far.add(best_cid)
        concept_use_counts[best_cid] += 1

print("Allocation:")
for s, c in allocation.items():
    print(f"  Scene {s}: {c}")
diversity = validate_concept_diversity(allocation, num_scenes)
print("Diversity:", diversity)
