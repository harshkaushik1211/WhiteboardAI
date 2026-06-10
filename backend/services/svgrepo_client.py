"""Download SVG files from https://www.svgrepo.com/ (CC0 icons).

Uses the CDN show URL (works with a browser User-Agent). Search/list pages are often
blocked for automated clients; pass explicit icon URLs from the site.
"""
from __future__ import annotations

import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
BASE = "https://www.svgrepo.com"
URL_PATTERNS = [
    re.compile(r"svgrepo\.com/svg/(\d+)/([a-zA-Z0-9_-]+)/?", re.I),
    re.compile(r"svgrepo\.com/download/(\d+)/([a-zA-Z0-9_-]+)\.svg", re.I),
    re.compile(r"svgrepo\.com/show/(\d+)/([a-zA-Z0-9_-]+)\.svg", re.I),
]


@dataclass
class SvgRepoRef:
    icon_id: str
    slug: str

    @property
    def show_url(self) -> str:
        return f"{BASE}/show/{self.icon_id}/{self.slug}.svg"


def parse_svgrepo_url(url: str) -> SvgRepoRef:
    for pattern in URL_PATTERNS:
        m = pattern.search(url.strip())
        if m:
            return SvgRepoRef(icon_id=m.group(1), slug=m.group(2))
    raise ValueError(
        f"Not a recognized SVG Repo URL: {url}\n"
        "Expected e.g. https://www.svgrepo.com/svg/489281/api"
    )


def fetch_svg(ref: SvgRepoRef, timeout: float = 30.0) -> str:
    req = urllib.request.Request(
        ref.show_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "image/svg+xml,text/xml,application/xml,*/*",
            "Referer": f"{BASE}/svg/{ref.icon_id}/{ref.slug}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} for {ref.show_url}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error for {ref.show_url}: {e}") from e

    if not _looks_like_svg(data):
        raise RuntimeError(
            f"Response is not SVG (bot checkpoint or rate limit?). "
            f"Open {BASE}/svg/{ref.icon_id}/{ref.slug} in a browser, copy the URL, and retry later."
        )
    return data


def _looks_like_svg(text: str) -> bool:
    head = text.lstrip()[:800].lower()
    if "vercel security checkpoint" in head or "<!doctype html" in head:
        return False
    return "<svg" in head


def save_to_assets(
    content: str,
    assets_root: Path,
    category: str,
    concept: str,
    *,
    replace: bool = False,
) -> Path:
    out_dir = assets_root / category
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{concept}.svg"
    if dest.exists() and not replace:
        raise FileExistsError(f"{dest} exists (use replace=True)")
    dest.write_text(content, encoding="utf-8")
    return dest


@dataclass
class DownloadItem:
    url: str
    concept: str
    category: str = "biology"
    replace: bool = True
    icon_id: Optional[str] = None
    slug: Optional[str] = None


def download_item(
    item: DownloadItem,
    assets_root: Path,
    delay_sec: float = 1.2,
) -> Path:
    if item.icon_id and item.slug:
        ref = SvgRepoRef(item.icon_id, item.slug)
    else:
        ref = parse_svgrepo_url(item.url)
    content = fetch_svg(ref)
    path = save_to_assets(
        content, assets_root, item.category, item.concept, replace=item.replace
    )
    if delay_sec > 0:
        time.sleep(delay_sec)
    return path


def download_batch(
    items: List[DownloadItem],
    assets_root: Path,
    delay_sec: float = 1.2,
) -> List[Tuple[DownloadItem, Path]]:
    results: List[Tuple[DownloadItem, Path]] = []
    for i, item in enumerate(items):
        if i > 0 and delay_sec > 0:
            time.sleep(delay_sec)
        path = download_item(item, assets_root, delay_sec=0)
        results.append((item, path))
    return results
