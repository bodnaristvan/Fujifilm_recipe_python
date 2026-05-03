#!/usr/bin/env python3
"""
scrape_recipes.py — scrape film simulation recipes from fujixweekly.com

Saves one JSON file per recipe to recipes/builtin/<sensor>/
Downloads one sample image per recipe to recipes/builtin/<sensor>/images/

Usage:
    pip install requests beautifulsoup4
    python scrape_recipes.py [--sensor SENSOR] [--dry-run] [--limit N]

Options:
    --sensor    Sensor folder name: x-trans-v (default) or x-trans-iv
    --dry-run   Print discovered URLs without fetching/saving anything
    --limit N   Only scrape the first N recipes (useful for testing)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SENSOR_CONFIG: dict[str, dict] = {
    "x-trans-v": {
        "index_url": "https://fujixweekly.com/fujifilm-x-trans-v-recipes/",
        "output_dir": Path("recipes/builtin/x-trans-v"),
    },
    "x-trans-iv": {
        "index_url": "https://fujixweekly.com/fujifilm-x-trans-iv-recipes/",
        "output_dir": Path("recipes/builtin/x-trans-iv"),
    },
}

REQUEST_DELAY = 1.5   # seconds between requests — be polite

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Map text key variants → canonical JSON key
PARAM_MAP: dict[str, str] = {
    "film simulation":        "filmSimulation",
    "dynamic range":          "dynamicRange",
    "d-range priority":       "dRangePriority",
    "d range priority":       "dRangePriority",
    "grain effect":           "grainEffect",
    "grain roughness":        "grainRoughness",
    "color chrome effect":    "colorChrome",
    "color chrome fx blue":   "colorChromeFxBlue",
    "white balance":          "whiteBalance",
    "highlight":              "highlight",
    "shadow":                 "shadow",
    "color":                  "color",
    "sharpness":              "sharpness",
    "high iso nr":            "noiseReduction",
    "noise reduction":        "noiseReduction",
    "clarity":                "clarity",
    "iso":                    "iso",
    "exposure compensation":  "exposureCompensation",
    "smooth skin effect":     "smoothSkin",
    "smooth skin":            "smoothSkin",
}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def get_soup(url: str, session: requests.Session) -> BeautifulSoup:
    resp = session.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return BeautifulSoup(resp.content, "html.parser")


def download_image(url: str, dest: Path, session: requests.Session) -> bool:
    """Download image bytes to *dest*. Returns True on success."""
    if not url:
        return False
    try:
        resp = session.get(url, headers=HEADERS, timeout=30, stream=True)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return True
    except Exception as exc:
        print(f"    [!]  Image download failed ({exc})")
        return False


# ---------------------------------------------------------------------------
# Index page scraping
# ---------------------------------------------------------------------------

# Matches individual recipe pages:
#   /2024/03/27/some-slug/             — dated path (most recipes)
#   /1971-kodak-a-fujifilm-recipe-for-x-trans-v-cameras/  — undated, newer format
# Explicitly excludes category index pages like /fujifilm-x-trans-v-recipes/
_RECIPE_PATH_RE = re.compile(
    r"^https://fujixweekly\.com/"
    r"(?:"
    r"\d{4}/\d{2}/\d{2}/[^/?#]+"          # dated path
    r"|"
    r"[^/?#]+-fujifilm-recipe-for-[^/?#]*" # undated "X-fujifilm-recipe-for-Y" format
    r")/?$"
)


def get_recipe_urls(soup: BeautifulSoup) -> list[tuple[str, str]]:
    """Return [(recipe_url, thumbnail_url), …] from the index page."""
    seen: set[str] = set()
    results: list[tuple[str, str]] = []

    for a in soup.find_all("a", href=True):
        href: str = a["href"].rstrip("/") + "/"
        if href in seen:
            continue
        if not _RECIPE_PATH_RE.match(href):
            continue

        # Best thumbnail: the <img> immediately before this <a> in the DOM
        thumb = ""
        prev = a.find_previous_sibling()
        if isinstance(prev, Tag) and prev.name == "img":
            src = prev.get("src", "")
            thumb = src.split("?")[0]   # drop resize query params
        else:
            # Also check inside any wrapper: look for a child/sibling img
            for img in a.find_all_previous("img", limit=3):
                src = img.get("src", "")
                if "wp-content/uploads" in src or "i0.wp.com" in src:
                    thumb = src.split("?")[0]
                    break

        seen.add(href)
        results.append((href, thumb))

    return results


# ---------------------------------------------------------------------------
# Recipe page scraping
# ---------------------------------------------------------------------------

def get_article_content(soup: BeautifulSoup) -> Tag | None:
    """Return the main article content div."""
    return (
        soup.find("div", class_="entry-content")
        or soup.find("div", class_="post-content")
        or soup.find("article")
    )


def parse_params(soup: BeautifulSoup) -> dict[str, str]:
    """
    Extract recipe parameters from the article body.

    New format — each param on its own line inside <p>:
        Film Simulation: Classic Chrome
        Dynamic Range: DR200
        ...

    Old format — pipe-separated <strong> block where the first segment is
    the unlabelled film simulation name:
        Classic Chrome | Dynamic Range: DR200 | Highlight: 0 | ...
    """
    content = get_article_content(soup)
    if content is None:
        content = soup

    params: dict[str, str] = {}

    for p in content.find_all("p"):
        raw = p.get_text(separator="\n")
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]

        # Old format: first line is the bare film sim name, no "Key:" prefix.
        # e.g. "<strong>Classic Chrome\nDynamic Range: DR200\n..."
        # Links inside the <strong> can split "Acros (+Y, +R, +G)" into 3 lines,
        # so check if ANY of the next 3 lines contains a Key:Value pair.
        if (
            "filmSimulation" not in params
            and len(lines) >= 2
            and ":" not in lines[0]
            and len(lines[0]) < 40
            and re.match(r"^[A-Za-z][A-Za-z0-9 \-/.+(),]+$", lines[0])
            and any(":" in lines[i] for i in range(1, min(4, len(lines))))
        ):
            params["filmSimulation"] = lines[0].rstrip(" (")

        for line in lines:
            # "Key: Value" or "Key:Value"
            m = re.match(r"^([A-Za-z][A-Za-z0-9 \-/()]+?):\s*(.+)$", line)
            if not m:
                continue
            key_raw = m.group(1).strip().lower()
            value = m.group(2).strip()

            canonical = PARAM_MAP.get(key_raw)
            if canonical and canonical not in params:
                # Film sim values like "Acros (" are truncated due to inline links
                # splitting the remainder onto a new line — strip the dangling paren.
                if canonical == "filmSimulation":
                    value = value.rstrip(" (")
                params[canonical] = value

    return params


def get_first_article_image(soup: BeautifulSoup) -> str:
    """
    Return the URL of the first suitable sample photo in the article body.
    Strips WordPress resize query params so we get the original quality.
    """
    content = get_article_content(soup)
    if content is None:
        return ""

    for img in content.find_all("img"):
        src: str = img.get("src", "")
        if not src:
            continue
        # Must be a real upload, not a UI sprite / icon
        if "wp-content/uploads" in src or "i0.wp.com" in src:
            return src.split("?")[0]

    return ""


def _get_page_title(soup: BeautifulSoup) -> str:
    """Raw H1/H2 page title."""
    for selector in (
        ("h1", {"class": re.compile(r"entry-title|post-title")}),
        ("h2", {"class": re.compile(r"entry-title|post-title")}),
        ("h1", {}),
        ("h2", {}),
    ):
        tag, attrs = selector
        el = soup.find(tag, attrs) if attrs else soup.find(tag)
        if el:
            return el.get_text(strip=True)
    return ""


# Curly/angled opening+closing quote pairs used on fujixweekly
_QUOTED_NAME = re.compile(r'[“‘«‹]([^”’»›]{2,60})[”’»›]')


def _clean_page_title(title: str) -> str:
    """Extract a short recipe name from a verbose fujixweekly post title.

    Examples:
      "Fujifilm X-E4 Film Simulation Recipe: Kodachrome 25"  → "Kodachrome 25"
      "Kodak Portra 160 — Fujifilm X100V Film Simulation Recipe" → "Kodak Portra 160"
      "McCurry Kodachrome — A Fujifilm X-Trans IV Film Simulation Recipe" → "McCurry Kodachrome"
    """
    # "... Recipe: RecipeName"  →  take RecipeName
    m = re.search(r'[Rr]ecipes?:\s*(.+)$', title)
    if m:
        return m.group(1).strip()

    # "RecipeName — [A ]Fujifilm ..."  →  take RecipeName
    m = re.match(r'^(.+?)\s+[—–\-]+\s+(?:A\s+)?Fujifilm', title)
    if m:
        return m.group(1).strip()

    # Strip trailing boilerplate
    title = re.sub(r'\s+[—–\-]+\s+Fujifilm.*', '', title).strip()
    title = re.sub(r'\s+[Ff]ilm [Ss]imulation [Rr]ecipes?\b.*', '', title).strip()
    return title


def get_recipe_name(soup: BeautifulSoup) -> str:
    """Return a clean recipe name for display.

    Primary: quoted name in the first figcaption, e.g.
        'Autumn on Kodachrome – UT – X-E4 – "Kodachrome 25"'  →  'Kodachrome 25'
    Fallback: clean up the verbose H1 page title.
    """
    content = get_article_content(soup)
    if content:
        for fig in content.find_all("figcaption"):
            text = fig.get_text(" ", strip=True)
            m = _QUOTED_NAME.search(text)
            if m:
                return m.group(1).strip()

    return _clean_page_title(_get_page_title(soup))


# ---------------------------------------------------------------------------
# Slug helpers
# ---------------------------------------------------------------------------

def slug_from_url(url: str) -> str:
    """Derive a filesystem-safe slug from the recipe URL."""
    path = urlparse(url).path.rstrip("/")
    slug = path.split("/")[-1]
    # Trim the camera/sensor suffix the site appends
    slug = re.sub(r"-fujifilm-.*", "", slug)
    slug = re.sub(r"-film-simulation.*", "", slug)
    # Sanitise
    slug = re.sub(r"[^a-z0-9\-]", "-", slug.lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug[:80]


def image_filename(slug: str, image_url: str) -> str:
    ext = os.path.splitext(urlparse(image_url).path)[1] or ".jpg"
    return f"{slug}{ext}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Fujifilm recipes from fujixweekly.com")
    parser.add_argument(
        "--sensor",
        choices=list(SENSOR_CONFIG),
        default="x-trans-v",
        help="Sensor generation to scrape (default: x-trans-v)",
    )
    parser.add_argument("--dry-run", action="store_true", help="List URLs only, don't save")
    parser.add_argument("--limit", type=int, default=0, help="Max recipes to scrape (0 = all)")
    parser.add_argument(
        "--patch-titles", action="store_true",
        help="Re-fetch existing recipes and update only the title field",
    )
    args = parser.parse_args()

    cfg = SENSOR_CONFIG[args.sensor]
    INDEX_URL = cfg["index_url"]
    OUTPUT_DIR = cfg["output_dir"]
    IMAGE_DIR = OUTPUT_DIR / "images"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()

    # ---- Patch-titles mode: update title field in existing JSONs ----
    if args.patch_titles:
        json_files = sorted(f for f in OUTPUT_DIR.glob("*.json") if f.name != "_index.json")
        if args.limit:
            json_files = json_files[: args.limit]
        print(f"[*] Patching titles for {len(json_files)} recipes in {OUTPUT_DIR}")
        updated = errors = 0
        for i, json_path in enumerate(json_files, 1):
            data = json.loads(json_path.read_text(encoding="utf-8"))
            url = data.get("source", "")
            if not url:
                continue
            try:
                time.sleep(REQUEST_DELAY)
                soup = get_soup(url, session)
                new_title = get_recipe_name(soup)
                old_title = data.get("title", "")
                if new_title and new_title != old_title:
                    data["title"] = new_title
                    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
                    print(f"[{i:>3}/{len(json_files)}] {json_path.name}")
                    print(f"    old: {old_title!r}")
                    print(f"    new: {new_title!r}")
                    updated += 1
                else:
                    print(f"[{i:>3}/{len(json_files)}] [ok]  {json_path.name}")
            except Exception as exc:
                print(f"[{i:>3}/{len(json_files)}] [ERR] {json_path.name}: {exc}")
                errors += 1
        print(f"\n  Updated: {updated}  Errors: {errors}")
        return

    # ---- Step 1: collect recipe URLs from index ----
    print(f"[*] Sensor  : {args.sensor}")
    print(f"[*] Fetching index: {INDEX_URL}")
    index_soup = get_soup(INDEX_URL, session)
    all_urls = get_recipe_urls(index_soup)

    if args.limit:
        all_urls = all_urls[: args.limit]

    print(f"   Found {len(all_urls)} recipe links\n")

    if args.dry_run:
        for url, thumb in all_urls:
            print(f"  {url}")
            if thumb:
                print(f"    thumb: {thumb}")
        return

    # ---- Step 2: scrape each recipe ----
    saved_slugs: list[str] = []
    skipped = 0
    errors = 0

    for i, (url, thumb_url) in enumerate(all_urls, 1):
        slug = slug_from_url(url)
        out_path = OUTPUT_DIR / f"{slug}.json"

        if out_path.exists():
            print(f"[{i:>3}/{len(all_urls)}] [skip]  {slug}  (already scraped)")
            saved_slugs.append(slug)
            skipped += 1
            continue

        print(f"[{i:>3}/{len(all_urls)}] [>] {url}")

        try:
            time.sleep(REQUEST_DELAY)
            soup = get_soup(url, session)

            title = get_recipe_name(soup)
            params = parse_params(soup)
            img_url = get_first_article_image(soup) or thumb_url

            # Download image
            img_file = ""
            if img_url:
                img_file = image_filename(slug, img_url)
                img_dest = IMAGE_DIR / img_file
                if img_dest.exists():
                    print(f"    [img]  Image already on disk: {img_file}")
                elif download_image(img_url, img_dest, session):
                    print(f"    [img]  Downloaded: {img_file}")
                else:
                    img_file = ""

            recipe = {
                "slug": slug,
                "title": title,
                "source": url,
                "image": img_file,
                "params": params,
            }

            n_params = len(params)
            if n_params < 5:
                # Not a recipe page — article/roundup/tips post, skip it
                print(f"    [!]  Only {n_params} params — looks like a non-recipe page, skipping")
                errors += 1
                continue

            out_path.write_text(
                json.dumps(recipe, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"    [OK] Saved {slug}.json  ({n_params} params parsed)")
            saved_slugs.append(slug)

        except Exception as exc:
            print(f"    [ERR] ERROR: {exc}")
            errors += 1

    # ---- Step 3: write index ----
    index_file = OUTPUT_DIR / "_index.json"
    index_file.write_text(json.dumps(saved_slugs, indent=2), encoding="utf-8")

    print("\n" + "-" * 60)
    print(f"  Total recipes : {len(all_urls)}")
    print(f"  Saved         : {len(saved_slugs) - skipped}")
    print(f"  Skipped (dup) : {skipped}")
    print(f"  Errors        : {errors}")
    print(f"  Output dir    : {OUTPUT_DIR.resolve()}")
    print("-" * 60)


if __name__ == "__main__":
    main()
