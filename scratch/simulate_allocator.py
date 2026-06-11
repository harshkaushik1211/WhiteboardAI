import sys
from pathlib import Path
sys.path.append("c:/Users/harsh/OneDrive/Desktop/WhiteboardAI/backend")

from models.schemas import ConceptGraph, EducationalConcept, ConceptRelationship, LessonPlan
from services.concept_decomposer import validate_concept_diversity, validate_coverage

def get_physics_graph() -> ConceptGraph:
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
    edges = [
        ConceptRelationship(from_concept="force", to_concept="acceleration", relationship_type="causes"),
        ConceptRelationship(from_concept="mass", to_concept="acceleration", relationship_type="resists"),
    ]
    return ConceptGraph(topic="Newton's Laws", domain="physics", concepts=concepts, edges=edges)

def get_chemistry_graph() -> ConceptGraph:
    concepts = [
        EducationalConcept(concept_id="ph_scale", name="pH Scale", importance=0.95, visual_priority=0.85, concept_type="system"),
        EducationalConcept(concept_id="acid", name="Acid", importance=0.90, visual_priority=0.80, concept_type="input"),
        EducationalConcept(concept_id="base", name="Base", importance=0.90, visual_priority=0.80, concept_type="input"),
        EducationalConcept(concept_id="hydrogen_ion", name="Hydrogen Ion", importance=0.85, visual_priority=0.70, concept_type="component", prerequisite_concepts=["acid"]),
        EducationalConcept(concept_id="hydroxide_ion", name="Hydroxide Ion", importance=0.85, visual_priority=0.70, concept_type="component", prerequisite_concepts=["base"]),
        EducationalConcept(concept_id="water", name="Water", importance=0.80, visual_priority=0.85, concept_type="output", prerequisite_concepts=["hydrogen_ion", "hydroxide_ion"]),
        EducationalConcept(concept_id="salt", name="Salt", importance=0.75, visual_priority=0.75, concept_type="output", prerequisite_concepts=["acid", "base"]),
        EducationalConcept(concept_id="neutralization", name="Neutralization", importance=0.80, visual_priority=0.75, concept_type="process", prerequisite_concepts=["acid", "base"]),
        EducationalConcept(concept_id="flask", name="Flask", importance=0.60, visual_priority=0.90, concept_type="object"),
        EducationalConcept(concept_id="litmus_paper", name="Litmus Paper", importance=0.70, visual_priority=0.90, concept_type="component"),
    ]
    edges = [
        ConceptRelationship(from_concept="acid", to_concept="hydrogen_ion", relationship_type="releases"),
    ]
    return ConceptGraph(topic="Acids and Bases", domain="chemistry", concepts=concepts, edges=edges)

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
    edges = [
        ConceptRelationship(from_concept="scheduler", to_concept="cpu", relationship_type="allocates"),
    ]
    return ConceptGraph(topic="Operating Systems", domain="computer_science", concepts=concepts, edges=edges)

def get_math_graph() -> ConceptGraph:
    concepts = [
        EducationalConcept(concept_id="vector", name="Vector", importance=0.95, visual_priority=0.85, concept_type="object"),
        EducationalConcept(concept_id="magnitude", name="Magnitude", importance=0.90, visual_priority=0.75, concept_type="formula", prerequisite_concepts=["vector"]),
        EducationalConcept(concept_id="direction", name="Direction", importance=0.90, visual_priority=0.75, concept_type="formula", prerequisite_concepts=["vector"]),
        EducationalConcept(concept_id="scalar", name="Scalar", importance=0.80, visual_priority=0.70, concept_type="input"),
        EducationalConcept(concept_id="vector_addition", name="Vector Addition", importance=0.85, visual_priority=0.80, concept_type="process", prerequisite_concepts=["vector"]),
        EducationalConcept(concept_id="resultant", name="Resultant", importance=0.90, visual_priority=0.80, concept_type="output", prerequisite_concepts=["vector_addition"]),
        EducationalConcept(concept_id="dot_product", name="Dot Product", importance=0.80, visual_priority=0.70, concept_type="process", prerequisite_concepts=["vector"]),
        EducationalConcept(concept_id="arrow_curved", name="Arrow", importance=0.50, visual_priority=0.90, concept_type="component"),
    ]
    edges = [
        ConceptRelationship(from_concept="vector", to_concept="magnitude", relationship_type="has"),
    ]
    return ConceptGraph(topic="Vectors", domain="mathematics", concepts=concepts, edges=edges)

def simulate_allocate(
    concept_graph: ConceptGraph,
    lesson_plan: LessonPlan,
    num_scenes: int,
    consec_penalty_val: float,
    new_penalty_val: float,
    use_ceil_formula: bool,
) -> dict:
    concepts = concept_graph.concepts
    if not concepts:
        return {i: [] for i in range(1, num_scenes + 1)}

    in_degree = {c.concept_id: 0 for c in concepts}
    adj = {c.concept_id: [] for c in concepts}
    concepts_by_id = {c.concept_id: c for c in concepts}

    for c in concepts:
        for prereq in c.prerequisite_concepts:
            if prereq in adj:
                adj[prereq].append(c.concept_id)
                in_degree[c.concept_id] += 1

    TYPE_WEIGHTS = {
        "input": 1, "actor": 2, "object": 3, "component": 4, "formula": 5,
        "cause": 6, "process": 7, "state": 8, "effect": 9, "output": 10,
        "comparison": 11, "system": 12,
    }
    def get_sort_key(concept_id: str):
        c = concepts_by_id[concept_id]
        w = TYPE_WEIGHTS.get(c.concept_type, 6)
        return (w, -c.importance, -c.visual_priority)

    sources = [cid for cid, deg in in_degree.items() if deg == 0]
    sources.sort(key=get_sort_key)

    sorted_concept_ids = []
    while sources:
        u = sources.pop(0)
        sorted_concept_ids.append(u)
        for v in adj[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                sources.append(v)
        sources.sort(key=get_sort_key)

    for c in concepts:
        if c.concept_id not in sorted_concept_ids:
            sorted_concept_ids.append(c.concept_id)

    # Budget - Dynamic based on complexity and graph size
    complexity = (lesson_plan.concept_complexity or "medium").lower()
    if complexity == "simple":
        target_per_scene = min(3, max(2, len(concepts) // 3))
    elif complexity == "complex":
        target_per_scene = min(6, max(4, len(concepts) // 2))
    else:
        target_per_scene = min(5, max(3, len(concepts) // 2))

    allocation = {s: [] for s in range(1, num_scenes + 1)}
    concept_use_counts = {cid: 0 for cid in sorted_concept_ids}

    def get_max_reuse(importance: float) -> int:
        if importance > 0.8:
            return 3
        elif importance >= 0.5:
            return 2
        return 1

    for s in range(1, num_scenes + 1):
        new_selected = 0
        used_so_far = {cid for cid, count in concept_use_counts.items() if count > 0}

        remaining = len(sorted_concept_ids) - len(used_so_far)
        remaining_scenes = num_scenes - s + 1
        
        if use_ceil_formula:
            max_new_per_scene = max(1, (remaining + remaining_scenes - 1) // remaining_scenes)
            if s == 1:
                max_new_per_scene = target_per_scene
        else:
            max_new_per_scene = max(2, len(concepts) // num_scenes + 1)

        for slot in range(target_per_scene):
            candidates = []
            for idx, cid in enumerate(sorted_concept_ids):
                c = concepts_by_id[cid]
                current_uses = concept_use_counts[cid]
                max_uses = get_max_reuse(c.importance)

                if cid in allocation[s] or current_uses >= max_uses:
                    continue

                is_new = (cid not in used_so_far)

                new_penalty = 0.0
                if is_new and new_selected >= max_new_per_scene:
                    new_penalty = new_penalty_val

                ideal_scene = int(idx * num_scenes / len(sorted_concept_ids)) + 1
                progression_fit = 1.0 - abs(s - ideal_scene) / num_scenes

                coverage_need = 1.5 if current_uses == 0 else 0.0

                consec_penalty = 0.0
                if s > 1 and cid in allocation[s - 1]:
                    consec_penalty = consec_penalty_val

                prereq_penalty = 0.0
                for prereq in c.prerequisite_concepts:
                    assigned_previously = False
                    for prev_s in range(1, s + 1):
                        if prereq in allocation[prev_s]:
                            assigned_previously = True
                            break
                    if not assigned_previously:
                        prereq_penalty += 1.5

                score = (
                    c.importance
                    + c.visual_priority
                    + coverage_need
                    + 0.5 * progression_fit
                    - consec_penalty
                    - prereq_penalty
                    - new_penalty
                )
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

    # Cleanup pass
    for cid in sorted_concept_ids:
        if concept_use_counts[cid] == 0:
            idx = sorted_concept_ids.index(cid)
            ideal_s = min(int(idx * num_scenes / len(sorted_concept_ids)) + 1, num_scenes)
            allocation[ideal_s].append(cid)
            concept_use_counts[cid] += 1

    return allocation

# Run simulations and print failures
subjects = [
    ("Physics", get_physics_graph(), LessonPlan(concept_complexity="complex")),
    ("Chemistry", get_chemistry_graph(), LessonPlan(concept_complexity="medium")),
    ("Computer Science", get_cs_graph(), LessonPlan(concept_complexity="complex")),
    ("Mathematics", get_math_graph(), LessonPlan(concept_complexity="simple")),
]

best_cases = []
for cp in [1.5, 2.5, 3.5, 4.5]:
    for np in [3.0, 4.0, 5.0, 6.0]:
        for ceil_formula in [True, False]:
            failures = 0
            for name, graph, lp in subjects:
                allocation = simulate_allocate(graph, lp, 6, cp, np, ceil_formula)
                diversity = validate_concept_diversity(allocation, 6)
                coverage = validate_coverage(graph, lp, allocation)

                overlap = diversity["overlap_ratio"]
                novelty = diversity["visual_novelty_score"]
                cov_rate = coverage["coverage_rate"]
                type_bal = coverage["concept_type_balance"]
                reuse_bal = coverage["concept_reuse_balance"]

                complexity = (lp.concept_complexity or "medium").lower()
                if complexity == "simple":
                    t_density = min(3, max(2, len(graph.concepts) // 3))
                elif complexity == "complex":
                    t_density = min(6, max(4, len(graph.concepts) // 2))
                else:
                    t_density = min(5, max(3, len(graph.concepts) // 2))

                target_overlap = min(0.38, max(0.20, len(graph.concepts) / (6 * t_density) * 1.1))

                is_overlap_ok = overlap < target_overlap
                is_novel = novelty > 0.70
                is_covered = cov_rate >= 0.90
                is_type_ok = type_bal >= 0.80
                is_reuse_ok = reuse_bal >= 0.70

                if not (is_overlap_ok and is_novel and is_covered and is_type_ok and is_reuse_ok):
                    failures += 1
            best_cases.append((failures, cp, np, ceil_formula))

best_cases.sort()
print("Top 10 configurations with dynamic target_per_scene and overlap threshold:")
for rank, (failures, cp, np, ceil) in enumerate(best_cases[:10]):
    print(f"Rank {rank+1}: Failures={failures}, cp={cp}, np={np}, ceil={ceil}")
    for name, graph, lp in subjects:
        allocation = simulate_allocate(graph, lp, 6, cp, np, ceil)
        diversity = validate_concept_diversity(allocation, 6)
        coverage = validate_coverage(graph, lp, allocation)
        
        complexity = (lp.concept_complexity or "medium").lower()
        if complexity == "simple":
            t_density = min(3, max(2, len(graph.concepts) // 3))
        elif complexity == "complex":
            t_density = min(6, max(4, len(graph.concepts) // 2))
        else:
            t_density = min(5, max(3, len(graph.concepts) // 2))
        target_overlap = min(0.38, max(0.20, len(graph.concepts) / (6 * t_density) * 1.1))
        
        print(f"  {name:<20}: Overlap={diversity['overlap_ratio']:.2f} (Target={target_overlap:.2f}), Novelty={diversity['visual_novelty_score']:.2f}, Coverage={coverage['coverage_rate']:.2f}")
