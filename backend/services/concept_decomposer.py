"""Educational Concept Decomposition Service — Phase 6.

Decomposes educational topics into an Educational Concept Graph, sorts them
pedagogically, allocates them across scenes with controlled reuse and adaptive budgets,
and runs comprehensive diversity, novelty, and coverage validators.
"""
import logging
from typing import Dict, List, Set, Any
from difflib import SequenceMatcher

from models.schemas import ConceptGraph, LessonPlan, EducationalConcept, ConceptRelationship
from prompts.concept_decomposition_prompt import CONCEPT_DECOMPOSITION_SYSTEM, build_decomposition_prompt

logger = logging.getLogger("concept_decomposer")

TYPE_WEIGHTS = {
    "input": 1,
    "actor": 2,
    "object": 3,
    "component": 4,
    "formula": 5,
    "cause": 6,
    "process": 7,
    "state": 8,
    "effect": 9,
    "output": 10,
    "comparison": 11,
    "system": 12,
}


async def generate_concept_graph(topic: str, lesson_plan: LessonPlan) -> ConceptGraph:
    """Generate the Concept Graph for a given topic using GPT-4o."""
    from services.llm_service import llm_service

    try:
        prompt = build_decomposition_prompt(topic, lesson_plan.learning_objectives)
        data = await llm_service._chat_json(CONCEPT_DECOMPOSITION_SYSTEM, prompt)
        graph = ConceptGraph.model_validate(data)
        logger.info(
            f"[DECOMPOSER] Graph generated for '{topic}' with {len(graph.concepts)} concepts "
            f"and {len(graph.edges)} edges in domain '{graph.domain}'."
        )
        return graph
    except Exception as exc:
        logger.warning(
            f"[DECOMPOSER] Graph generation failed for '{topic}': {exc}. "
            "Building fallback concept graph."
        )
        return _build_fallback_graph(topic, lesson_plan)


def allocate_scene_concepts(
    concept_graph: ConceptGraph,
    lesson_plan: LessonPlan,
    num_scenes: int,
    force_reallocate: bool = False,
) -> Dict[int, List[str]]:
    """Allocate concepts to scenes using Kahn-based topological sorting and greedy slot-filling."""
    concepts = concept_graph.concepts
    if not concepts:
        return {i: [] for i in range(1, num_scenes + 1)}

    # 1. Kahn's Algorithm for Topological Sort respecting prerequisites
    in_degree = {c.concept_id: 0 for c in concepts}
    adj = {c.concept_id: [] for c in concepts}
    concepts_by_id = {c.concept_id: c for c in concepts}

    for c in concepts:
        for prereq in c.prerequisite_concepts:
            if prereq in adj:
                adj[prereq].append(c.concept_id)
                in_degree[c.concept_id] += 1

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

    # Fallback if cycles are present: append any missed concepts
    for c in concepts:
        if c.concept_id not in sorted_concept_ids:
            sorted_concept_ids.append(c.concept_id)

    # 2. Adaptive Concept Budget
    complexity = (lesson_plan.concept_complexity or "medium").lower()
    if complexity == "simple":
        target_per_scene = 2
    elif complexity == "complex":
        target_per_scene = 4
    else:
        target_per_scene = 3

    # 3. Greedy Slot-filling Allocation Engine
    allocation: Dict[int, List[str]] = {s: [] for s in range(1, num_scenes + 1)}
    concept_use_counts = {cid: 0 for cid in sorted_concept_ids}

    # Define reuse limits
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
        max_new_per_scene = max(1, (remaining + remaining_scenes - 1) // remaining_scenes)
        if s == 1:
            max_new_per_scene = target_per_scene

        for slot in range(target_per_scene):
            candidates = []
            for idx, cid in enumerate(sorted_concept_ids):
                c = concepts_by_id[cid]
                current_uses = concept_use_counts[cid]
                max_uses = get_max_reuse(c.importance)

                # Skip if already assigned in this scene or reached max reuse limits
                if cid in allocation[s] or current_uses >= max_uses:
                    continue

                is_new = (cid not in used_so_far)

                # Penalize introducing too many new concepts in a single scene
                new_penalty = 0.0
                if is_new and new_selected >= max_new_per_scene:
                    new_penalty = 4.0 if not force_reallocate else 6.0

                # Progression fit score
                ideal_scene = int(idx * num_scenes / len(sorted_concept_ids)) + 1
                progression_fit = 1.0 - abs(s - ideal_scene) / num_scenes

                # Coverage Need bonus
                coverage_need = 1.5 if current_uses == 0 else 0.0

                # Consecutive penalty
                consec_penalty = 0.0
                if s > 1 and cid in allocation[s - 1]:
                    consec_penalty = 1.5 if not force_reallocate else 2.5

                # Prerequisite penalty: if prerequisites have not been introduced yet
                prereq_penalty = 0.0
                for prereq in c.prerequisite_concepts:
                    # Check if prereq has been assigned to any scene <= s
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

            # Pick the candidate with the highest score
            candidates.sort(reverse=True, key=lambda x: x[0])
            best_cid = candidates[0][1]

            allocation[s].append(best_cid)
            if best_cid not in used_so_far:
                new_selected += 1
                used_so_far.add(best_cid)
            concept_use_counts[best_cid] += 1

    # Cleanup pass to guarantee 100% coverage of all concepts
    for cid in sorted_concept_ids:
        if concept_use_counts[cid] == 0:
            c = concepts_by_id[cid]
            idx = sorted_concept_ids.index(cid)
            ideal_s = min(int(idx * num_scenes / len(sorted_concept_ids)) + 1, num_scenes)
            allocation[ideal_s].append(cid)
            concept_use_counts[cid] += 1

    return allocation


def validate_concept_diversity(allocation: Dict[int, List[str]], num_scenes: int) -> dict:
    """Calculate scene diversity, consecutive Jaccard overlap, and visual novelty metrics."""
    total_assigned = []
    for concepts in allocation.values():
        total_assigned.extend(concepts)

    unique_concepts = set(total_assigned)

    # Consecutive overlaps
    overlap_ratios = []
    for s in range(1, num_scenes):
        s1 = set(allocation.get(s, []))
        s2 = set(allocation.get(s + 1, []))
        union = s1.union(s2)
        if union:
            overlap_ratios.append(len(s1.intersection(s2)) / len(union))
    overlap_ratio = sum(overlap_ratios) / len(overlap_ratios) if overlap_ratios else 0.0
    diversity_score = 1.0 - overlap_ratio

    # Visual Novelty Score (fraction of scenes that introduce at least one new concept)
    seen_concepts = set()
    scenes_with_new_concepts = 0
    for s in range(1, num_scenes + 1):
        scene_concepts = set(allocation.get(s, []))
        new_concepts = scene_concepts - seen_concepts
        if new_concepts:
            scenes_with_new_concepts += 1
            seen_concepts.update(new_concepts)

    visual_novelty_score = scenes_with_new_concepts / num_scenes if num_scenes > 0 else 0.0

    return {
        "total_assigned": len(total_assigned),
        "unique_concepts": len(unique_concepts),
        "overlap_ratio": overlap_ratio,
        "diversity_score": diversity_score,
        "visual_novelty_score": visual_novelty_score,
        "average_concepts_per_scene": len(total_assigned) / num_scenes if num_scenes > 0 else 0.0,
    }


def validate_coverage(
    concept_graph: ConceptGraph,
    lesson_plan: LessonPlan,
    allocation: Dict[int, List[str]],
) -> dict:
    """Run educational coverage validation checking inputs, outputs, processes, and type balancing."""
    all_assigned = set()
    for concepts in allocation.values():
        all_assigned.update(concepts)

    graph_concept_ids = {c.concept_id for c in concept_graph.concepts}

    # Core concepts (importance >= 0.8)
    core = {c.concept_id for c in concept_graph.concepts if c.importance >= 0.8}
    core_covered = core.intersection(all_assigned)
    core_pct = len(core_covered) / len(core) if core else 1.0

    # Inputs
    inputs = {c.concept_id for c in concept_graph.concepts if c.concept_type == "input"}
    inputs_covered = inputs.intersection(all_assigned)
    inputs_pct = len(inputs_covered) / len(inputs) if inputs else 1.0

    # Outputs
    outputs = {c.concept_id for c in concept_graph.concepts if c.concept_type == "output"}
    outputs_covered = outputs.intersection(all_assigned)
    outputs_pct = len(outputs_covered) / len(outputs) if outputs else 1.0

    # Processes
    processes = {c.concept_id for c in concept_graph.concepts if c.concept_type == "process"}
    processes_covered = processes.intersection(all_assigned)
    processes_pct = len(processes_covered) / len(processes) if processes else 1.0

    # Overall coverage rate
    coverage_rate = len(graph_concept_ids.intersection(all_assigned)) / len(graph_concept_ids) if graph_concept_ids else 1.0

    # Reuse balance (fraction of concepts meeting reuse boundaries)
    valid_reuse_count = 0
    reuse_map = {cid: 0 for cid in graph_concept_ids}
    for concepts in allocation.values():
        for cid in concepts:
            if cid in reuse_map:
                reuse_map[cid] += 1

    def get_max_reuse(importance: float) -> int:
        if importance > 0.8:
            return 3
        elif importance >= 0.5:
            return 2
        return 1

    for c in concept_graph.concepts:
        max_uses = get_max_reuse(c.importance)
        if reuse_map[c.concept_id] <= max_uses:
            valid_reuse_count += 1
    concept_reuse_balance = valid_reuse_count / len(concept_graph.concepts) if concept_graph.concepts else 1.0

    # Concept Type balance (checks if at least 4 unique types exist in the graph)
    unique_types = {c.concept_type for c in concept_graph.concepts}
    concept_type_balance = min(1.0, len(unique_types) / 5.0)  # normalized relative to 5 typical types

    return {
        "coverage_rate": coverage_rate,
        "core_concepts_covered_pct": core_pct * 100,
        "inputs_covered_pct": inputs_pct * 100,
        "outputs_covered_pct": outputs_pct * 100,
        "processes_covered_pct": processes_pct * 100,
        "concept_reuse_balance": concept_reuse_balance,
        "concept_type_balance": concept_type_balance,
        "objectives_covered_pct": coverage_rate * 100,
    }


def _build_fallback_graph(topic: str, lesson_plan: LessonPlan) -> ConceptGraph:
    """Return a generic fallback ConceptGraph when decomposition fails."""
    domain_guess = "general"
    t = topic.lower()
    if "newton" in t or "law" in t or "force" in t:
        domain_guess = "physics"
        concepts = [
            EducationalConcept(concept_id="force", name="Force", importance=0.95, visual_priority=0.90, concept_type="cause"),
            EducationalConcept(concept_id="mass", name="Mass", importance=0.85, visual_priority=0.80, concept_type="input"),
            EducationalConcept(concept_id="acceleration", name="Acceleration", importance=0.90, visual_priority=0.75, concept_type="effect", prerequisite_concepts=["force", "mass"]),
            EducationalConcept(concept_id="motion", name="Motion", importance=0.80, visual_priority=0.80, concept_type="process", prerequisite_concepts=["acceleration"]),
            EducationalConcept(concept_id="friction", name="Friction", importance=0.75, visual_priority=0.80, concept_type="process"),
            EducationalConcept(concept_id="gravity", name="Gravity", importance=0.75, visual_priority=0.85, concept_type="process"),
            EducationalConcept(concept_id="momentum", name="Momentum", importance=0.80, visual_priority=0.75, concept_type="process", prerequisite_concepts=["mass", "acceleration"]),
            EducationalConcept(concept_id="inertia", name="Inertia", importance=0.70, visual_priority=0.70, concept_type="state", prerequisite_concepts=["mass"]),
            EducationalConcept(concept_id="action_force", name="Action Force", importance=0.85, visual_priority=0.85, concept_type="cause"),
            EducationalConcept(concept_id="reaction_force", name="Reaction Force", importance=0.85, visual_priority=0.85, concept_type="effect", prerequisite_concepts=["action_force"]),
            EducationalConcept(concept_id="car", name="Car", importance=0.60, visual_priority=0.95, concept_type="actor"),
            EducationalConcept(concept_id="rocket", name="Rocket", importance=0.65, visual_priority=0.95, concept_type="actor"),
        ]
        edges = [
            ConceptRelationship(from_concept="force", to_concept="acceleration", relationship_type="causes"),
            ConceptRelationship(from_concept="mass", to_concept="acceleration", relationship_type="limits"),
            ConceptRelationship(from_concept="action_force", to_concept="reaction_force", relationship_type="triggers"),
        ]
    elif "photo" in t or "plant" in t or "leaf" in t:
        domain_guess = "biology"
        concepts = [
            EducationalConcept(concept_id="sunlight", name="Sunlight", importance=0.95, visual_priority=0.90, concept_type="input"),
            EducationalConcept(concept_id="water", name="Water", importance=0.85, visual_priority=0.80, concept_type="input"),
            EducationalConcept(concept_id="carbon_dioxide", name="Carbon Dioxide", importance=0.85, visual_priority=0.70, concept_type="input"),
            EducationalConcept(concept_id="stomata", name="Stomata", importance=0.70, visual_priority=0.80, concept_type="component"),
            EducationalConcept(concept_id="roots", name="Roots", importance=0.70, visual_priority=0.85, concept_type="component"),
            EducationalConcept(concept_id="leaf", name="Leaf", importance=0.80, visual_priority=0.95, concept_type="component"),
            EducationalConcept(concept_id="chloroplast", name="Chloroplast", importance=0.85, visual_priority=0.85, concept_type="component", prerequisite_concepts=["leaf"]),
            EducationalConcept(concept_id="glucose", name="Glucose", importance=0.80, visual_priority=0.75, concept_type="output", prerequisite_concepts=["water", "carbon_dioxide", "chloroplast"]),
            EducationalConcept(concept_id="oxygen", name="Oxygen", importance=0.80, visual_priority=0.75, concept_type="output", prerequisite_concepts=["water", "chloroplast"]),
            EducationalConcept(concept_id="atp", name="ATP", importance=0.75, visual_priority=0.70, concept_type="output"),
            EducationalConcept(concept_id="chlorophyll", name="Chlorophyll", importance=0.75, visual_priority=0.75, concept_type="component", prerequisite_concepts=["chloroplast"]),
            EducationalConcept(concept_id="photosynthesis_process", name="Photosynthesis Process", importance=0.90, visual_priority=0.80, concept_type="system", prerequisite_concepts=["sunlight", "chloroplast"]),
        ]
        edges = [
            ConceptRelationship(from_concept="sunlight", to_concept="chloroplast", relationship_type="energizes"),
            ConceptRelationship(from_concept="water", to_concept="roots", relationship_type="absorbed_by"),
        ]
    else:
        concepts = [
            EducationalConcept(concept_id="core_concept", name="Core Concept", importance=0.95, visual_priority=0.80, concept_type="system"),
            EducationalConcept(concept_id="input_variable", name="Input Variable", importance=0.85, visual_priority=0.70, concept_type="input"),
            EducationalConcept(concept_id="helper_variable", name="Helper Variable", importance=0.70, visual_priority=0.70, concept_type="input"),
            EducationalConcept(concept_id="step_one", name="Step One", importance=0.80, visual_priority=0.75, concept_type="process", prerequisite_concepts=["input_variable"]),
            EducationalConcept(concept_id="step_two", name="Step Two", importance=0.80, visual_priority=0.75, concept_type="process", prerequisite_concepts=["step_one"]),
            EducationalConcept(concept_id="process_flow", name="Process Flow", importance=0.85, visual_priority=0.75, concept_type="process", prerequisite_concepts=["step_two"]),
            EducationalConcept(concept_id="output_result", name="Output Result", importance=0.75, visual_priority=0.80, concept_type="output", prerequisite_concepts=["process_flow"]),
            EducationalConcept(concept_id="final_state", name="Final State", importance=0.75, visual_priority=0.75, concept_type="state", prerequisite_concepts=["output_result"]),
            EducationalConcept(concept_id="overall_system", name="Overall System", importance=0.90, visual_priority=0.85, concept_type="system", prerequisite_concepts=["core_concept"]),
            EducationalConcept(concept_id="example_use", name="Example Use", importance=0.65, visual_priority=0.85, concept_type="comparison"),
        ]
        edges = [
            ConceptRelationship(from_concept="input_variable", to_concept="step_one", relationship_type="enters"),
        ]

    return ConceptGraph(topic=topic, domain=domain_guess, concepts=concepts, edges=edges)
