#!/usr/bin/env python3
"""Generate curated educational outline SVG assets for the semantic library."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "assets"
STROKE = "#1a1a2e"
SW = "2.5"


def wrap(viewbox: str, content: str) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" fill="none" stroke="{STROKE}" stroke-width="{SW}" stroke-linecap="round" stroke-linejoin="round">
{content}
</svg>'''


ASSETS = {
    "biology": {
        "lungs": wrap("0 0 200 240", '''<path d="M100,40 L100,90" data-path-length="50"/>
<path d="M100,90 Q40,90 35,140 Q30,200 60,220 Q80,230 100,200" data-path-length="200"/>
<path d="M100,90 Q160,90 165,140 Q170,200 140,220 Q120,230 100,200" data-path-length="200"/>
<path d="M70,120 L130,120" data-path-length="60"/>'''),
        "mitochondria": wrap("0 0 200 120", '''<ellipse cx="100" cy="60" rx="85" ry="45" data-path-length="400"/>
<path d="M30,60 L170,60 M50,45 L50,75 M75,40 L75,80 M100,35 L100,85 M125,40 L125,80 M150,45 L150,75" data-path-length="350"/>'''),
        "cell": wrap("0 0 200 160", '''<ellipse cx="100" cy="80" rx="85" ry="60" data-path-length="450"/>
<circle cx="100" cy="80" r="22" data-path-length="140"/>
<path d="M55,70 Q100,110 145,70" data-path-length="120"/>'''),
        "oxygen": wrap("0 0 120 120", '''<circle cx="45" cy="60" r="18" data-path-length="115"/>
<circle cx="75" cy="60" r="18" data-path-length="115"/>
<path d="M63,60 L57,60" data-path-length="10"/>'''),
        "glucose": wrap("0 0 140 140", '''<polygon points="70,20 110,45 110,95 70,120 30,95 30,45" data-path-length="400"/>
<circle cx="70" cy="70" r="12" data-path-length="75"/>'''),
        "bloodstream": wrap("0 0 200 80", '''<path d="M10,40 Q50,20 100,40 T190,40" data-path-length="250"/>
<path d="M10,50 Q50,70 100,50 T190,50" data-path-length="250"/>'''),
        "atp": wrap("0 0 160 100", '''<circle cx="50" cy="50" r="35" data-path-length="220"/>
<path d="M90,35 L130,35 M90,50 L120,50 M90,65 L130,65" data-path-length="100"/>
<text x="38" y="58" font-size="28" fill="{STROKE}" stroke="none" font-family="sans-serif">ATP</text>'''.replace("{STROKE}", STROKE)),
        "leaf": wrap("0 0 120 180", '''<path d="M60,170 L60,90" data-path-length="80"/>
<path d="M60,90 Q20,70 25,40 Q40,15 60,50 Q80,15 95,40 Q100,70 60,90" data-path-length="280"/>'''),
        "chloroplast": wrap("0 0 200 100", '''<ellipse cx="100" cy="50" rx="90" ry="40" data-path-length="400"/>
<path d="M25,50 L175,50 M50,35 L50,65 M80,30 L80,70 M120,30 L120,70 M150,35 L150,65" data-path-length="300"/>'''),
        "dna": wrap("0 0 100 200", '''<path d="M35,20 Q65,50 35,80 Q5,110 35,140 Q65,170 35,200" data-path-length="350"/>
<path d="M65,20 Q35,50 65,80 Q95,110 65,140 Q35,170 65,200" data-path-length="350"/>
<path d="M35,50 L65,50 M35,100 L65,100 M35,150 L65,150" data-path-length="150"/>'''),
        "heart": wrap("0 0 120 110", '''<path d="M60,95 Q20,55 35,35 Q60,10 60,40 Q60,10 85,35 Q100,55 60,95" data-path-length="350"/>'''),
        "brain": wrap("0 0 140 120", '''<path d="M70,100 Q25,80 30,50 Q40,15 70,25 Q100,15 110,50 Q115,80 70,100" data-path-length="400"/>
<path d="M50,55 Q70,65 90,55 M45,75 Q70,85 95,75" data-path-length="80"/>'''),
        "bacteria": wrap("0 0 160 80", '''<ellipse cx="80" cy="40" rx="70" ry="30" data-path-length="350"/>
<path d="M30,40 L50,40 M110,40 L130,40" data-path-length="40"/>'''),
    },
    "chemistry": {
        "atom": wrap("0 0 160 160", '''<circle cx="80" cy="80" r="8" data-path-length="50"/>
<ellipse cx="80" cy="80" rx="55" ry="20" data-path-length="250"/>
<ellipse cx="80" cy="80" rx="55" ry="20" transform="rotate(60 80 80)" data-path-length="250"/>
<ellipse cx="80" cy="80" rx="55" ry="20" transform="rotate(120 80 80)" data-path-length="250"/>'''),
        "molecule": wrap("0 0 140 100", '''<circle cx="40" cy="50" r="20" data-path-length="125"/>
<circle cx="100" cy="50" r="20" data-path-length="125"/>
<path d="M60,50 L80,50" data-path-length="20"/>'''),
        "flask": wrap("0 0 100 180", '''<path d="M35,25 L65,25 L70,80 Q78,150 50,165 Q22,150 30,80 Z" data-path-length="450"/>
<path d="M42,100 L58,100" data-path-length="16"/>'''),
        "co2": wrap("0 0 140 80", '''<text x="10" y="55" font-size="36" fill="{STROKE}" stroke="none">CO</text>
<text x="72" y="40" font-size="22" fill="{STROKE}" stroke="none">2</text>'''.replace("{STROKE}", STROKE)),
        "o2": wrap("0 0 100 80", '''<circle cx="35" cy="40" r="18" data-path-length="115"/>
<circle cx="65" cy="40" r="18" data-path-length="115"/>
<path d="M53,40 L47,40" data-path-length="6"/>'''),
    },
    "physics": {
        "car": wrap("0 0 200 120", '''<path d="M40,90 L55,60 L145,60 L160,90 L175,90 L175,105 L40,105 Z" data-path-length="400"/>
<circle cx="70" cy="105" r="14" data-path-length="90"/>
<circle cx="150" cy="105" r="14" data-path-length="90"/>'''),
        "ball": wrap("0 0 100 100", '''<circle cx="50" cy="50" r="40" data-path-length="250"/>'''),
        "rocket": wrap("0 0 100 200", '''<path d="M50,25 L65,95 L50,85 L35,95 Z" data-path-length="200"/>
<path d="M35,95 L20,140 L35,115 M65,95 L80,140 L65,115" data-path-length="150"/>
<path d="M42,95 L42,165 L58,165 L58,95" data-path-length="150"/>'''),
        "force": wrap("0 0 160 60", '''<path d="M10,30 L120,30 M95,15 L120,30 L95,45" data-path-length="180"/>'''),
        "friction": wrap("0 0 120 80", '''<path d="M10,50 L90,50" data-path-length="80"/>
<path d="M30,50 L25,65 M50,50 L45,68 M70,50 L75,65" data-path-length="60"/>'''),
        "pulley": wrap("0 0 100 120", '''<circle cx="50" cy="40" r="30" data-path-length="190"/>
<path d="M50,70 L50,110 M20,110 L80,110" data-path-length="100"/>'''),
        "magnet": wrap("0 0 120 140", '''<path d="M40,30 L40,110 Q40,130 60,130 Q80,130 80,110 L80,30" data-path-length="350"/>
<path d="M40,30 L25,15 M80,30 L95,15" data-path-length="50"/>'''),
        "wave": wrap("0 0 200 80", '''<path d="M10,40 Q40,10 70,40 T130,40 T190,40" data-path-length="300"/>'''),
        "lightbulb": wrap("0 0 100 160", '''<path d="M50,20 Q25,20 25,55 Q25,90 40,100 L40,120 L60,120 L60,100 Q75,90 75,55 Q75,20 50,20" data-path-length="400"/>
<path d="M42,135 L58,135 M45,148 L55,148" data-path-length="40"/>'''),
    },
    "math": {
        "array": wrap("0 0 200 80", '''<rect x="20" y="25" width="30" height="30" data-path-length="120"/>
<rect x="60" y="25" width="30" height="30" data-path-length="120"/>
<rect x="100" y="25" width="30" height="30" data-path-length="120"/>
<rect x="140" y="25" width="30" height="30" data-path-length="120"/>
<rect x="180" y="25" width="30" height="30" data-path-length="120"/>'''),
        "midpoint": wrap("0 0 200 60", '''<path d="M20,30 L180,30" data-path-length="160"/>
<circle cx="100" cy="30" r="8" data-path-length="50"/>
<path d="M100,15 L100,45" data-path-length="30"/>'''),
        "sorted_list": wrap("0 0 200 100", '''<rect x="20" y="40" width="25" height="40" data-path-length="130"/>
<rect x="55" y="30" width="25" height="50" data-path-length="150"/>
<rect x="90" y="20" width="25" height="60" data-path-length="170"/>
<rect x="125" y="10" width="25" height="70" data-path-length="190"/>
<path d="M15,85 L185,85" data-path-length="170"/>'''),
        "pointer": wrap("0 0 80 100", '''<path d="M40,10 L55,50 L45,50 L60,90 L20,55 L32,55 Z" data-path-length="250"/>'''),
        "chart_bar": wrap("0 0 160 120", '''<path d="M20,100 L20,70 L50,100 L50,50 L80,100 L80,35 L110,100 L110,60 L140,100" data-path-length="400"/>'''),
    },
    "computer_science": {
        "server": wrap("0 0 100 160", '''<rect x="20" y="20" width="60" height="120" rx="4" data-path-length="360"/>
<path d="M32,45 L68,45 M32,70 L68,70 M32,95 L68,95 M32,120 L68,120" data-path-length="200"/>'''),
        "client": wrap("0 0 120 100", '''<rect x="25" y="15" width="70" height="50" rx="3" data-path-length="240"/>
<path d="M45,65 L75,65 L60,85 Z" data-path-length="80"/>'''),
        "laptop": wrap("0 0 140 100", '''<rect x="25" y="15" width="90" height="55" rx="3" data-path-length="290"/>
<path d="M10,70 L130,70 L120,85 L20,85 Z" data-path-length="280"/>'''),
        "packet": wrap("0 0 120 80", '''<rect x="15" y="20" width="90" height="45" rx="4" data-path-length="270"/>
<path d="M25,35 L95,35 M25,50 L70,50" data-path-length="100"/>'''),
        "cloud": wrap("0 0 160 90", '''<path d="M40,60 Q20,60 30,40 Q25,15 60,25 Q80,5 110,25 Q145,20 135,45 Q150,65 120,65 L40,65 Z" data-path-length="500"/>'''),
        "database": wrap("0 0 100 120", '''<ellipse cx="50" cy="30" rx="40" ry="15" data-path-length="180"/>
<path d="M10,30 L10,90 Q10,105 50,105 Q90,105 90,90 L90,30" data-path-length="280"/>
<ellipse cx="50" cy="90" rx="40" ry="15" data-path-length="180"/>'''),
        "handshake": wrap("0 0 200 100", '''<path d="M30,60 L70,40 L100,55 L130,35 L170,55" data-path-length="280"/>
<path d="M70,40 L70,70 M130,35 L130,65" data-path-length="60"/>'''),
    },
    "humans": {
        "human": wrap("0 0 100 200", '''<circle cx="50" cy="35" r="22" data-path-length="140"/>
<path d="M50,57 L50,120" data-path-length="63"/>
<path d="M25,85 L75,85" data-path-length="50"/>
<path d="M50,120 L30,175" data-path-length="58"/>
<path d="M50,120 L70,175" data-path-length="58"/>'''),
        "person": wrap("0 0 100 200", '''<circle cx="50" cy="35" r="22" data-path-length="140"/>
<path d="M50,57 L50,120" data-path-length="63"/>
<path d="M25,85 L75,85" data-path-length="50"/>
<path d="M50,120 L30,175 M50,120 L70,175" data-path-length="116"/>'''),
    },
    "icons/arrows": {
        "arrow-right": wrap("0 0 120 40", '''<path d="M5,20 L95,20 M75,8 L95,20 L75,32" data-path-length="150"/>'''),
        "arrow-left": wrap("0 0 120 40", '''<path d="M115,20 L25,20 M45,8 L25,20 L45,32" data-path-length="150"/>'''),
        "arrow-up": wrap("0 0 40 120", '''<path d="M20,115 L20,25 M8,45 L20,25 L32,45" data-path-length="150"/>'''),
        "arrow-down": wrap("0 0 40 120", '''<path d="M20,5 L20,95 M8,75 L20,95 L32,75" data-path-length="150"/>'''),
        "arrow-curved": wrap("0 0 100 80", '''<path d="M15,65 Q15,15 65,15 L85,15 M70,5 L85,15 L70,25" data-path-length="200"/>'''),
    },
    "diagrams": {
        "flow-box": wrap("0 0 140 80", '''<rect x="10" y="15" width="120" height="50" rx="8" data-path-length="340"/>'''),
        "pipeline-stage": wrap("0 0 120 100", '''<rect x="10" y="20" width="100" height="60" rx="6" data-path-length="320"/>
<path d="M60,80 L60,95" data-path-length="15"/>'''),
    },
}

EXTRA = {
    "biology": {"sun": "physics/lightbulb"},  # symlink concept - copy lightbulb as sun
    "icons": {"unknown-concept": wrap("0 0 100 100", '''<circle cx="50" cy="50" r="35" data-path-length="220"/>
<path d="M35,35 L65,65 M65,35 L35,65" data-path-length="85"/>''')},
}

def main():
    for category, items in ASSETS.items():
        out_dir = ROOT / category
        out_dir.mkdir(parents=True, exist_ok=True)
        for name, svg in items.items():
            (out_dir / f"{name}.svg").write_text(svg, encoding="utf-8")
            print(f"  {category}/{name}.svg")

    icons_dir = ROOT / "icons"
    icons_dir.mkdir(exist_ok=True)
    (icons_dir / "unknown-concept.svg").write_text(EXTRA["icons"]["unknown-concept"], encoding="utf-8")

    # sun for photosynthesis
    sun_svg = ASSETS["physics"]["lightbulb"].replace("lightbulb", "sun")
    (ROOT / "biology" / "sun.svg").write_text(ASSETS["physics"]["lightbulb"], encoding="utf-8")

    print(f"Generated {sum(len(v) for v in ASSETS.values()) + 1} assets")


if __name__ == "__main__":
    main()
