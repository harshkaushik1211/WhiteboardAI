"""Schedules visual elements and motion profiles sequentially to represent cause-effect transitions."""
from typing import Dict, List, Tuple
from models.schemas import SceneElement

def schedule_motion_timeline(
    elements: List[SceneElement],
    duration_sec: float,
) -> Dict[str, Tuple[float, float]]:
    """
    Computes (delay, duration) in seconds for each element,
    implementing sequenced reveal and cause-effect choreography.
    Returns a dict mapping element_id to (start_time_sec, end_time_sec).
    """
    timings: Dict[str, Tuple[float, float]] = {}
    
    # 1. Separate headlines and labels from active visual assets
    headlines = [el for el in elements if el.type in ("text", "label") and "headline" in el.id]
    visual_elements = [el for el in elements if el not in headlines]
    
    # Headlines exist throughout the entire scene
    for hl in headlines:
        timings[hl.id] = (0.0, duration_sec)
        
    n_visuals = len(visual_elements)
    if n_visuals == 0:
        return timings

    # 2. Check for Cause-Effect relationships safely using getattr
    # Target: Arrow appears -> Arrow advances (pushes) -> Object moves/accelerates
    has_cause_effect = any(
        getattr(el, "motion_profile", None) in ("force_push", "constraint_hold") or
        getattr(el, "relationship", None) in ("causes", "applied_to")
        for el in visual_elements
    )
    
    if has_cause_effect and n_visuals >= 2:
        arrow_el = None
        target_el = None
        
        for el in visual_elements:
            el_concept = (el.concept or "").lower()
            if el.type == "arrow" or "arrow" in el.id or el_concept in ("force", "arrow", "force_arrow"):
                arrow_el = el
            else:
                target_el = el
                
        if arrow_el and target_el:
            # Timeline segments:
            # 0% - 25% of duration: Draw target object (e.g. car)
            # 25% - 50% of duration: Draw force arrow
            # 50% - 75% of duration: Arrow advances (push motion)
            # 75% - 95% of duration: Target object accelerates
            # 95% - 100% of duration: Static hold for visual digestion
            t_obj_draw = duration_sec * 0.25
            t_arrow_draw = duration_sec * 0.25
            t_push = duration_sec * 0.25
            t_move = duration_sec * 0.20
            
            timings[target_el.id] = (0.0, duration_sec - 0.5)
            timings[arrow_el.id] = (t_obj_draw, t_obj_draw + t_arrow_draw + t_push)
            
            # Map any other visuals to fall between arrow and hold
            for el in visual_elements:
                if el.id not in timings:
                    timings[el.id] = (t_obj_draw, duration_sec - 1.0)
            return timings

    # Default sequence (Attention Management - reveal elements one after another)
    current_time = 0.5
    step_time = (duration_sec - 1.5) / max(n_visuals, 1)
    
    # Primary elements first
    sorted_visuals = sorted(
        visual_elements,
        key=lambda x: 0 if getattr(x, "importance", "secondary") == "primary" else 1
    )
    
    for el in sorted_visuals:
        draw_dur = max(1.5, step_time)
        draw_end = min(duration_sec - 0.5, current_time + draw_dur)
        timings[el.id] = (current_time, draw_end)
        current_time += step_time * 0.8
        
    return timings
