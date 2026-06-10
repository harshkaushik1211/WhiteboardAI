#!/usr/bin/env python3
"""Download SVG icons from https://www.svgrepo.com into assets/{category}/{concept}.svg

Examples:
  # Single icon (copy URL from the icon page in your browser)
  python3 scripts/download_svgrepo.py \\
    --url https://www.svgrepo.com/svg/489281/api \\
    --concept api --category computer_science

  # Batch from manifest
  python3 scripts/download_svgrepo.py --manifest assets/svgrepo_manifest.json

  # Then normalize + reindex
  python3 scripts/normalize_svg_assets.py
  curl -X POST http://localhost:8000/assets/reindex
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from services.svgrepo_client import DownloadItem, download_batch, download_item, parse_svgrepo_url  # noqa: E402

ASSETS = ROOT / "assets"
MANIFEST_DEFAULT = ASSETS / "svgrepo_manifest.json"


def load_manifest(path: Path) -> list[DownloadItem]:
    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("items", data) if isinstance(data, dict) else data
    items = []
    for row in raw:
        items.append(
            DownloadItem(
                url=row.get("url", ""),
                concept=row["concept"],
                category=row.get("category", "biology"),
                replace=row.get("replace", True),
                icon_id=row.get("id") or row.get("icon_id"),
                slug=row.get("slug"),
            )
        )
    return items


def main() -> int:
    p = argparse.ArgumentParser(description="Download SVGs from svgrepo.com")
    p.add_argument("--url", help="SVG Repo page or download URL")
    p.add_argument("--concept", help="Asset filename stem, e.g. lungs")
    p.add_argument("--category", default="biology", help="Subfolder under assets/")
    p.add_argument("--manifest", type=Path, help="JSON manifest with items[]")
    p.add_argument("--replace", action="store_true", default=True)
    p.add_argument("--no-replace", action="store_false", dest="replace")
    p.add_argument("--delay", type=float, default=1.2, help="Seconds between downloads")
    p.add_argument("--normalize", action="store_true", help="Run normalize_svg_assets.py after")
    p.add_argument("--reindex", action="store_true", help="Rebuild assets index after")
    p.add_argument("--dry-run", action="store_true", help="Parse URLs only, do not download")
    args = p.parse_args()

    if args.manifest:
        if not args.manifest.exists():
            print(f"Manifest not found: {args.manifest}", file=sys.stderr)
            return 1
        items = load_manifest(args.manifest)
    elif args.url and args.concept:
        items = [
            DownloadItem(
                url=args.url,
                concept=args.concept,
                category=args.category,
                replace=args.replace,
            )
        ]
    else:
        p.print_help()
        print("\nProvide --url + --concept, or --manifest", file=sys.stderr)
        return 1

    if args.dry_run:
        for item in items:
            ref = parse_svgrepo_url(item.url) if item.url else None
            print(f"  {item.concept} -> {ref.show_url if ref else item.icon_id}/{item.slug}")
        return 0

    print(f"Downloading {len(items)} icon(s) into {ASSETS} ...")
    try:
        results = download_batch(items, ASSETS, delay_sec=args.delay)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    for item, path in results:
        print(f"  OK {item.concept} -> {path.relative_to(ROOT)}")

    if args.normalize:
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "scripts" / "normalize_svg_assets.py")], check=True)

    if args.reindex:
        sys.path.insert(0, str(ROOT / "backend"))
        from services.svg_indexer import rebuild_index
        n = len(rebuild_index())
        print(f"Reindexed {n} assets")

    print("Done. Rebuild index: curl -X POST http://localhost:8000/assets/reindex")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
