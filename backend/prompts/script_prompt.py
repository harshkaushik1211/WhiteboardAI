# =============================================================================
# WHITEBOARD AI — EDUCATIONAL SCRIPT GENERATION ENGINE
# =============================================================================
#
# Philosophy: The AI is a TEACHER, not a narrator or summarizer.
#
# Every scene must BUILD INTUITION before naming a concept.
# Every script must TEACH, not merely DEFINE.
#
# Role models: Khan Academy, Crash Course, 3Blue1Brown, Feynman Lectures,
#              Veritasium, Physics Wallah, TED-Ed
# =============================================================================

SCRIPT_SYSTEM_PROMPT = """You are an expert educational teacher creating whiteboard explainer video scripts.

Your teaching heroes are:
- Sal Khan (Khan Academy) — patient, conversational, builds intuition one step at a time
- Richard Feynman — starts from everyday observation, makes complex ideas feel inevitable
- Crash Course hosts — energetic, witty, uses stories and pop-culture analogies
- 3Blue1Brown — builds visual-geometric intuition before any formal notation
- Physics Wallah — enthusiastic and relatable, connects concepts to student experience

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR CORE TEACHING PHILOSOPHY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Rule 1 — TEACH FIRST, DEFINE LATER
Every concept needs intuition before terminology.
Never open a scene by naming or defining the concept you're teaching.

Rule 2 — START WITH CURIOSITY
Open scenes with a question, a surprising observation, or a relatable scenario.
The student should be asking "why?" before you tell them the answer.

Rule 3 — USE ANALOGIES FOR ABSTRACT IDEAS
When a concept is not directly observable, find a concrete analogy:
  Electric current → water flowing through a pipe
  DNA             → instruction manual for building a living thing
  Computer memory → a notebook where you jot temporary notes
  Force           → the push or pull you feel with your own hands
  Energy transfer → passing a ball between friends

Rule 4 — CONNECT EVERY LESSON TO REAL LIFE
Every video must answer "Why should I care about this?"
Include at least one REAL_WORLD_APPLICATION scene that connects the concept
to something the student can see, touch, or relate to in everyday life.

Rule 5 — FLOW LIKE A LECTURE, NOT A TEXTBOOK
Scenes should connect naturally. Use transition phrases such as:
  "Now let's see why that happens..."
  "But there's more to this story."
  "Let's look at a concrete example."
  "This leads us directly to..."
  "Building on what we just discovered..."
  "So here's the big question..."

Rule 6 — USE QUESTIONS AND THOUGHT EXPERIMENTS
Before introducing major concepts, ask the student to predict:
  "What do you think will happen?"
  "Why doesn't the ball move on its own?"
  "Can you guess what comes next?"
Use these sparingly — maximum one per scene, only where they feel natural.

Rule 7 — ADAPT TO YOUR AUDIENCE
Match vocabulary, analogy sophistication, and explanation depth to the
educational level specified. A middle-school student and a college student
need completely different explanations of the same concept.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCENE STRUCTURE GUIDELINES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Each scene has a pedagogical role (scene_type). Use these intentionally:

HOOK              — Opens with a question, story, surprising fact, or relatable observation.
                    Never starts with a definition.
INTUITION         — Builds understanding through analogy or everyday example
                    BEFORE the concept is formally named.
EXPLANATION       — Formally introduces the concept AFTER intuition is established.
                    Even here, use conversational language.
EXAMPLE           — Applies the concept to a specific concrete case.
VISUALIZATION     — Describes what's being drawn on the whiteboard and how it helps.
COMPARISON        — Contrasts two related ideas to sharpen understanding.
CAUSE_EFFECT      — Explains what causes what and why the mechanism works.
FORMULA           — Introduces a mathematical or formal relationship.
                    Always explain what it means in plain language first.
SUMMARY           — Reinforces key insights. Doesn't just list facts — synthesizes.
REAL_WORLD_APPLICATION — Explicitly answers "why does this matter in real life?"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WHAT YOU MUST NEVER DO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✗ Never start a scene with a definition: "X is defined as Y."
✗ Never use meta-narration: "In this video, we will learn about..."
✗ Never use academic passive voice: "It can be observed that..."
✗ Never write filler: "As we mentioned earlier..." / "In conclusion..."
✗ Never sacrifice explanation quality for brevity.
✗ Never produce narration that sounds like a dictionary entry.
✗ Never skip real-world connection — every lesson must have at least one.
✗ Never assume the student already has intuition — build it every time.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NARRATION LENGTH PHILOSOPHY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Write the explanation a skilled teacher would give — not the shortest possible version.
Duration will be automatically adjusted to match your narration length.
Your only constraints:
  1. Each scene covers exactly ONE focused idea.
  2. Total video should stay close to the target duration.

Output valid JSON only. No markdown. No explanation outside the JSON."""


# ---------------------------------------------------------------------------
# Domain-specific real-world example banks
# Injected into user prompts to give the AI concrete, relatable examples
# ---------------------------------------------------------------------------

_DOMAIN_EXAMPLES = {
    "physics": (
        "football resting on a field, car braking suddenly on a wet road, rocket launching from Earth, "
        "bicycle wheels spinning after you stop pedalling, roller coaster going over a hill, "
        "magnet picking up paper clips, a ball thrown at an angle"
    ),
    "biology": (
        "plants making food from sunlight through leaves, blood carrying oxygen from lungs to muscles, "
        "cells dividing when a cut heals, heart pumping blood through the body, "
        "how vaccines teach the immune system, how bacteria become antibiotic-resistant"
    ),
    "chemistry": (
        "iron rusting on a bicycle left in the rain, cooking an egg in a pan, "
        "baking bread rising due to yeast, burning wood releasing heat and light, "
        "dissolving sugar in tea, mixing vinegar and baking soda (instant fizz)"
    ),
    "mathematics": (
        "splitting a pizza equally between friends, measuring the shortest route on a map, "
        "calculating sale discount at a shop, finding the optimal fence length for a garden, "
        "understanding loan interest accumulating over time"
    ),
    "computer_science": (
        "searching for a word in a book (binary search analogy), sorting a deck of playing cards "
        "(various sort algorithms), how GPS finds the fastest route (graph algorithms), "
        "how streaming video loads in chunks, why websites sometimes slow down under heavy traffic"
    ),
    "economics": (
        "price of bread rising when wheat harvest is poor, supply and demand at a local market, "
        "why concert tickets get expensive when a popular band tours, "
        "how inflation makes savings worth less over time"
    ),
    "history": (
        "how the printing press changed who could read, why trade routes shaped civilizations, "
        "how small events can trigger large historical changes, "
        "how technology shifts change the balance of power between nations"
    ),
    "general": (
        "everyday observations students encounter at home, school, or outdoors; "
        "sports and games; food preparation; weather patterns; "
        "smartphones and apps; social media algorithms; public transport"
    ),
}

# Educational level adaptation guidance
_LEVEL_GUIDANCE = {
    "middle_school": (
        "Use very simple vocabulary. Avoid all jargon — if you must use a term, immediately explain it "
        "in plain words. Explain everything as if the student has never heard of the topic. "
        "Use relatable examples from school life, sports, cooking, and daily home activities. "
        "Keep sentences short. Make it energetic and slightly playful — learning should feel fun."
    ),
    "high_school": (
        "Use clear, accessible language. Introduce subject terminology carefully — always after building "
        "intuition through analogy or example first. Connect to exam relevance where appropriate, "
        "but keep the tone engaging and conversational, not dry or formal. "
        "Assume basic familiarity with numbers and common scientific concepts."
    ),
    "college": (
        "Use precise subject vocabulary — but still introduce it after establishing conceptual intuition. "
        "Assume mathematical literacy and willingness to engage with mechanisms and edge cases. "
        "Go deeper into the 'why' behind principles. Connect to adjacent concepts and career relevance. "
        "Students at this level appreciate nuance and honest acknowledgment of complexity."
    ),
    "competitive_exam": (
        "Build rock-solid conceptual foundations — exam questions test genuine understanding, "
        "not memorization. Use mnemonics and pattern-recognition techniques. "
        "Explicitly flag common misconceptions and exam traps. Use comparison scenes to sharpen "
        "distinctions between easily confused concepts. Keep the tone rigorous but human and encouraging."
    ),
}

# Scene count by complexity × duration
_COMPLEXITY_SCENE_COUNTS = {
    "simple":  {"short": 5, "medium": 5, "long": 6},
    "medium":  {"short": 6, "medium": 7, "long": 9},
    "complex": {"short": 8, "medium": 10, "long": 12},
}


def _detect_domain(topic: str) -> str:
    """Heuristically detect the subject domain from the topic string."""
    t = topic.lower()
    if any(w in t for w in [
        "physics", "force", "motion", "energy", "wave", "quantum", "newton",
        "gravity", "velocity", "acceleration", "thermodynamics", "optics",
        "electricity", "magnetism", "momentum", "inertia", "friction",
    ]):
        return "physics"
    if any(w in t for w in [
        "biology", "cell", "dna", "evolution", "photosynthesis", "gene",
        "organ", "blood", "plant", "animal", "bacteria", "virus", "immune",
        "mitosis", "meiosis", "ecology", "digestion", "respiration",
    ]):
        return "biology"
    if any(w in t for w in [
        "chemistry", "reaction", "element", "compound", "acid", "bond",
        "molecule", "atom", "periodic", "oxidation", "reduction", "solution",
        "equilibrium", "titration", "organic",
    ]):
        return "chemistry"
    if any(w in t for w in [
        "math", "calculus", "algebra", "geometry", "trigonometry",
        "probability", "statistics", "equation", "integral", "derivative",
        "matrix", "vector", "function", "theorem", "proof",
    ]):
        return "mathematics"
    if any(w in t for w in [
        "computer", "algorithm", "programming", "code", "software",
        "data structure", "machine learning", "network", "database",
        "sorting", "searching", "recursion", "complexity", "binary",
    ]):
        return "computer_science"
    if any(w in t for w in [
        "economics", "market", "supply", "demand", "inflation",
        "gdp", "trade", "finance", "currency", "budget",
    ]):
        return "economics"
    if any(w in t for w in [
        "history", "war", "revolution", "empire", "civilization",
        "century", "ancient", "medieval", "colonial", "independence",
    ]):
        return "history"
    return "general"


def _duration_band(duration: int) -> str:
    if duration <= 50:
        return "short"
    if duration <= 100:
        return "medium"
    return "long"


def build_script_prompt(
    topic: str,
    duration: int,
    style: str,
    language: str,
    memory_hints: dict = None,
    educational_level: str = "high_school",
    lesson_plan: dict = None,
    concept_graph: dict = None,
    assigned_scene_concepts: dict = None,
) -> str:
    """Build the full educational script generation user prompt.

    Changes from original version:
    - Removed hard max_words cap (advisory word range replaces it)
    - Added educational_level-specific guidance block
    - Added domain-specific example suggestions
    - Integrated lesson_plan (learning objectives, scene sequence, examples)
    - Added scene_type and transition_phrase to required JSON output
    - Added quality_feedback injection for rewrite passes
    - Narration length is driven by teaching need, not word budgets
    - Phase 6: Injects concept graph and assigned scene concepts to guide scene topics.

    Args:
        topic: Subject to teach.
        duration: Target video duration in seconds (soft constraint).
        style: Visual style hint (whiteboard, etc.).
        language: Narration language.
        memory_hints: Topic-specific semantic memory hints.
        educational_level: Target audience level.
        lesson_plan: Pre-generated lesson plan dict from the lesson planner.
        concept_graph: Concept graph dictionary.
        assigned_scene_concepts: Mapping of scene index (str or int) to list of assigned concepts.

    Returns:
        User-facing prompt string for the script generation LLM call.
    """
    memory_hints = memory_hints or {}
    lesson_plan = lesson_plan or {}

    domain = _detect_domain(topic)
    domain_examples = _DOMAIN_EXAMPLES.get(domain, _DOMAIN_EXAMPLES["general"])
    level_guidance = _LEVEL_GUIDANCE.get(educational_level, _LEVEL_GUIDANCE["high_school"])

    # ── Scene count ──────────────────────────────────────────────────────────
    if lesson_plan.get("estimated_scene_count"):
        scene_count = int(lesson_plan["estimated_scene_count"])
    elif memory_hints.get("script_scenes"):
        scene_count = int(memory_hints["script_scenes"])
    else:
        complexity = lesson_plan.get("concept_complexity", "medium")
        band = _duration_band(duration)
        scene_count = _COMPLEXITY_SCENE_COUNTS.get(complexity, _COMPLEXITY_SCENE_COUNTS["medium"])[band]

    approx_per_scene = round(duration / scene_count, 0)
    # Advisory word range — NOT a hard limit. Quality > brevity.
    words_advisory_min = int(approx_per_scene * 1.8)
    words_advisory_max = int(approx_per_scene * 3.2)

    # ── Topic-specific memory guidance block ─────────────────────────────────
    guidance_block = ""
    if memory_hints.get("script_guidance"):
        guidance_block = f"\nTopic-specific guidance: {memory_hints['script_guidance']}\n"

    # ── Lesson plan integration block ─────────────────────────────────────────
    lesson_block = ""
    if lesson_plan:
        objectives = lesson_plan.get("learning_objectives", [])
        seq = lesson_plan.get("scene_sequence", [])
        examples = lesson_plan.get("recommended_examples", [])
        misconceptions = lesson_plan.get("common_misconceptions", [])
        prerequisites = lesson_plan.get("prerequisites", [])
        attention_profile = lesson_plan.get("attention_profile", educational_level)
        quality_feedback = lesson_plan.get("quality_feedback", [])
        structured_feedback = lesson_plan.get("structured_feedback", {})

        if objectives:
            lesson_block += "\nLEARNING OBJECTIVES (what the student must understand by the end):\n"
            for obj in objectives:
                lesson_block += f"  • {obj}\n"

        if seq:
            lesson_block += f"\nSUGGESTED SCENE SEQUENCE: {' → '.join(seq)}\n"

        if prerequisites:
            lesson_block += "\nPREREQUISITE KNOWLEDGE (assume the student already knows these):\n"
            for prereq in prerequisites:
                lesson_block += f"  • {prereq}\n"

        if misconceptions:
            lesson_block += "\nCOMMON MISCONCEPTIONS TO ADDRESS AND DEBUNK:\n"
            for mis in misconceptions:
                lesson_block += f"  • {mis} (Address this naturally in the narration)\n"

        if examples:
            lesson_block += f"\nRECOMMENDED EXAMPLES TO USE: {', '.join(examples)}\n"

        # Attention profile guidelines
        lesson_block += f"\nATTENTION PROFILE GUIDELINE ({attention_profile}):\n"
        if attention_profile == "middle_school":
            lesson_block += "  - Target: Middle School. Maintain higher hook frequency, more concrete real-world objects, and high curiosity.\n"
        elif attention_profile == "college":
            lesson_block += "  - Target: College. Prioritize explanation depth, conceptual accuracy, and precise terminology.\n"
        elif attention_profile == "competitive_exam":
            lesson_block += "  - Target: Competitive Exams. Build conceptual foundations, address pitfalls, and point out common exam traps.\n"
        else:
            lesson_block += "  - Target: High School. Balance logical scaffolding with clear analogies.\n"

        if structured_feedback:
            lesson_block += "\nDETAILED REVIEW FEEDBACK FROM PREVIOUS VERSION:\n"
            for dim, detail in structured_feedback.items():
                if isinstance(detail, dict):
                    rating = detail.get("rating", "unknown").upper()
                    reason = detail.get("reason", "")
                    if rating in ("WEAK", "POOR", "MISSING", "INCOMPLETE"):
                        lesson_block += f"  ⚠ {dim.replace('_', ' ').title()}: [{rating}] — {reason}\n"
            lesson_block += "The script was rejected because of the above pedagogical issues. Correct all of them.\n"
        elif quality_feedback:
            lesson_block += "\nQUALITY FEEDBACK FROM PREVIOUS ATTEMPT (FIX THESE ISSUES):\n"
            for issue in quality_feedback:
                lesson_block += f"  ⚠ {issue}\n"
            lesson_block += "The previous script was rejected for the above reasons. Fix all of them.\n"

    # ── Concept graph and allocation integration block ───────────────────────
    allocation_block = ""
    if assigned_scene_concepts:
        allocation_block += "\nCRITICAL: CONCEPTS ASSIGNED TO EACH SCENE (You MUST write the scene narration and whiteboard visual description focusing primarily on explaining/illustrating these specific concepts):\n"
        for s_idx in range(1, scene_count + 1):
            s_key = str(s_idx)
            concepts_list = assigned_scene_concepts.get(s_key) or assigned_scene_concepts.get(s_idx) or []
            allocation_block += f"  Scene {s_idx}: {', '.join(concepts_list) if concepts_list else 'general discussion'}\n"
        allocation_block += "Do NOT explain all concepts in every scene. Establish a logical, progressive visual story utilizing the assigned list.\n"

    return f"""You are creating an educational whiteboard video script. Teach this topic as an expert teacher would.
{guidance_block}{lesson_block}{allocation_block}
━━━ PARAMETERS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Topic:              {topic}
Educational level:  {educational_level}
Language:           {language}
Visual style:       {style}
Target duration:    {duration} seconds (SOFT TARGET — educational quality takes priority)
Scene count:        {scene_count} scenes
~Seconds/scene:     ~{approx_per_scene:.0f} seconds each
Advisory word range per scene narration: {words_advisory_min}–{words_advisory_max} words
  (This is advisory only. Write full educational explanations. Do not truncate.)

━━━ EDUCATIONAL LEVEL GUIDANCE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{level_guidance}

━━━ REAL-WORLD EXAMPLES FOR THIS TOPIC (use these freely) ━━━━━━━━━━━━━━━━
{domain_examples}

━━━ REQUIRED TEACHING ARC ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Follow this general learning progression (adapt scene types to topic):
1. HOOK         — Open with a question, surprise, or relatable story. Never a definition.
2. INTUITION    — Build understanding through analogy/example BEFORE naming the concept.
3. EXPLANATION  — Formally introduce the concept after intuition is established.
4. EXAMPLE      — Show the concept applied to a specific concrete case.
5. [Optionally: FORMULA, COMPARISON, CAUSE_EFFECT, VISUALIZATION as needed]
6. REAL_WORLD_APPLICATION — Answer: "Why does this matter in real life?"
7. SUMMARY      — Reinforce key takeaways naturally. Synthesize, don't just list.

━━━ NARRATION WRITING RULES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REQUIRED:
  ✓ Scene 1 must start with a question, observation, or story — NOT a definition
  ✓ Use analogies for any abstract concept
  ✓ Include at least one REAL_WORLD_APPLICATION scene
  ✓ Every scene except the last must have a transition_phrase to the next
  ✓ Narration must sound like a teacher speaking to a curious student

FORBIDDEN:
  ✗ "X is defined as Y" — never start with a definition
  ✗ "In this video we will learn..." — meta-narration is banned
  ✗ Academic passive voice: "It can be observed that..."
  ✗ Cutting explanation short for brevity

━━━ VISUAL DESCRIPTION RULES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
visual_description should describe what to DRAW on the whiteboard while the narration plays.
Be specific: "Draw a football on the left, then animate an arrow pushing it to the right."
The visual must reinforce the narration — not contradict or repeat it in text form.

━━━ REQUIRED JSON OUTPUT FORMAT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{{
  "title": "Engaging, specific lesson title",
  "total_duration": {duration},
  "scenes": [
    {{
      "scene_id": 1,
      "scene_type": "HOOK",
      "narration": "Your complete teaching narration here. Write as much as needed to teach clearly. Do not truncate.",
      "visual_description": "Specific description of what to draw/animate on the whiteboard during this narration.",
      "keywords": ["keyword1", "keyword2"],
      "duration": {approx_per_scene:.1f},
      "transition_phrase": "Natural phrase that bridges to the next scene. E.g. 'Now let's understand why...'"
    }}
  ]
}}

scene_type must be one of:
HOOK | INTUITION | EXPLANATION | EXAMPLE | VISUALIZATION | COMPARISON | CAUSE_EFFECT | FORMULA | SUMMARY | REAL_WORLD_APPLICATION

FINAL CHECK before returning:
  □ Does scene 1 start with a question or observation (not a definition)?
  □ Is there at least one HOOK scene and one REAL_WORLD_APPLICATION scene?
  □ Do all scenes except the last have a transition_phrase?
  □ Does the narration sound like a teacher, not a textbook?
  □ Are there analogies or relatable examples for abstract concepts?

Output valid JSON only. No markdown. No text outside the JSON object."""
