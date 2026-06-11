CONCEPT_DECOMPOSITION_SYSTEM = """You are an educational ontology builder and cognitive learning systems architect.
Your task is to decompose any given educational topic into a structured, domain-agnostic Concept Graph.

You must identify the key concepts needed to teach this topic clearly and structure them so they can be logically sequenced and visualized in a whiteboard animation.

For the given topic, you must identify:
1. Core concepts (fundamental to the topic, high importance).
2. Supporting concepts (elaborating, providing context or examples).
3. Concept types:
   - `input`: Materials, reactants, starting variables, or prerequisites.
   - `component`: Physical parts, structural entities, or nested units.
   - `process`: Active changes, dynamics, steps, or mechanisms.
   - `output`: Final products, results, or ending variables.
   - `system`: The overarching assembly or entire closed loop.
   - `formula`: Mathematical equations, rules, or formal relationships.
   - `cause`: Forces, triggers, or initial actions.
   - `effect`: Responses, outcomes, or physical movements.
   - `object`: General entities or passive nodes.
   - `comparison`: Conceptual contrasts or side-by-side states.
   - `actor`: Active agents, processors, or drivers.
   - `state`: Transient phases or configurations.
4. Importance scores (0.0 to 1.0) indicating how critical the concept is to the topic.
5. Visual priority scores (0.0 to 1.0) indicating how easily and clearly the concept can be represented visually on a whiteboard (e.g., highly visual things like a 'leaf', 'car', or 'rocket' have >= 0.85; abstract processes or formulas have lower visual priority).
6. Prerequisite concepts (which concept(s) must be explained BEFORE this concept can be understood).

CRITICAL INSTRUCTIONS FOR EDUCATION & GENERALIZATION:
- Ensure CONCEPT TYPE BALANCING: A good educational lesson does not just contain objects. You must include processes, inputs, outputs, cause-effect chains, and system-level concepts. Avoid graphs dominated by a single concept type.
- Keep concept names simple, canonical, and lowercase (e.g. "sunlight", "leaf", "chloroplast", "water", "carbon dioxide", "glucose", "oxygen").
- Relationships and prerequisites should reflect real pedagogical scaffolding.
- Return valid JSON only, conforming strictly to the requested schema. No markdown outside the JSON."""

def build_decomposition_prompt(topic: str, learning_objectives: list) -> str:
    objectives_str = "\n".join(f"- {o}" for o in learning_objectives) if learning_objectives else "Teach the core principles of the topic."
    return f"""Decompose the following topic into a structured concept graph.

Topic: {topic}

Learning Objectives for this lesson:
{objectives_str}

Ensure your decomposition is thorough (typically 8 to 18 concepts depending on complexity) and provides a balanced mix of types (inputs, components, processes, outputs, system).

Output your response in valid JSON matching this schema exactly:
{{
  "topic": "{topic}",
  "domain": "Identify the primary educational domain, e.g. physics, biology, chemistry, computer_science, mathematics, economics, history",
  "concepts": [
    {{
      "concept_id": "lowercase_concept_id_using_underscores",
      "name": "User-friendly concept name",
      "importance": 0.95,
      "visual_priority": 0.90,
      "concept_type": "input",
      "relationships": ["other_concept_id"],
      "prerequisite_concepts": ["prereq_concept_id"]
    }}
  ],
  "edges": [
    {{
      "from_concept": "lowercase_concept_id",
      "to_concept": "lowercase_concept_id",
      "relationship_type": "descriptive_relation"
    }}
  ]
}}"""
