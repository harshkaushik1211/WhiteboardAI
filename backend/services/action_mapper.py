"""Maps semantic educational actions to executable motion profiles."""
from typing import Optional

ACTION_MAP = {
    "move": "translate",
    "accelerate": "translate_accelerate",
    "decelerate": "translate_decelerate",
    "roll": "roll_motion",
    "push": "force_push",
    "hold": "constraint_hold",
    "flow": "particle_flow",
    "react": "reaction_sequence",
    "compare": "comparison_highlight",
}

def map_action_to_motion(action: Optional[str]) -> str:
    """Resolve action to animation/motion profile, defaulting to stroke_reveal."""
    if not action:
        return "stroke_reveal"
    normalized = action.strip().lower()
    return ACTION_MAP.get(normalized, "stroke_reveal")
