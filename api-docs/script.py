"""Crawl The Odds API docs into local markdown via Jina Reader.

Run from this directory:
    python script.py
"""

from __future__ import annotations

import os
import time
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

# Seed pages + path prefixes that count as "docs we care about".
SEEDS = [
    "https://the-odds-api.com/liveapi/guides/v4/",
    "https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html",
    "https://the-odds-api.com/liveapi/guides/v4/samples.html",
    "https://the-odds-api.com/sports-odds-data/betting-markets.html",
    "https://the-odds-api.com/sports-odds-data/betting-markets-examples.html",
    "https://the-odds-api.com/sports-odds-data/bookmaker-apis.html",
    "https://the-odds-api.com/sports-odds-data/sports-apis.html",
    "https://the-odds-api.com/historical-odds-data/",
    "https://the-odds-api.com/releases/rotation-numbers.html",
]

ALLOWED_PREFIXES = (
    "https://the-odds-api.com/liveapi/",
    "https://the-odds-api.com/sports-odds-data/",
    "https://the-odds-api.com/historical-odds-data",
    "https://the-odds-api.com/releases/",
)

# Bare /guides/v4/ and /guides/v4/index.html are the same page — always save once
# under the index.html filename so we don't keep a duplicate.
CANONICAL_URLS = {
    "https://the-odds-api.com/liveapi/guides/v4": (
        "https://the-odds-api.com/liveapi/guides/v4/index.html"
    ),
    "https://the-odds-api.com/liveapi/guides/v4/": (
        "https://the-odds-api.com/liveapi/guides/v4/index.html"
    ),
}

OUTPUT_DIR = "docs_markdown"
SITE = "https://the-odds-api.com/"
SKIP_SUFFIXES = (".png", ".jpg", ".jpeg", ".css", ".js", ".svg", ".ico", ".xml", ".gif", ".webp")
# Broken / legacy paths linked from the live site that 404.
SKIP_URLS = {
    "https://the-odds-api.com/liveapi/guides/4/",
    "https://the-odds-api.com/liveapi/guides/4",
}


class LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for key, value in attrs:
            if key == "href" and value:
                self.hrefs.append(value)


def clean_filename(url: str) -> str:
    path = urlparse(url).path.strip("/").replace("/", "_")
    return path if path else "index"


def allowed(url: str) -> bool:
    return any(url.startswith(prefix) for prefix in ALLOWED_PREFIXES)


def fetch(url: str, timeout: int = 60) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "bet-bot-docs-crawl/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def normalize(url: str) -> str:
    return url.split("#")[0].split("?")[0]


os.makedirs(OUTPUT_DIR, exist_ok=True)

visited: set[str] = set()
saved_files: set[str] = set()
to_visit = list(SEEDS)
downloaded = 0
failed: list[tuple[str, str]] = []

print("Starting docs crawl...")

while to_visit:
    url = normalize(to_visit.pop(0))
    if not url or url in visited or url in SKIP_URLS or not allowed(url):
        continue

    visited.add(url)
    canonical = CANONICAL_URLS.get(url, url)
    filename = f"{clean_filename(canonical)}.md"
    if filename in saved_files:
        print(f"Skip duplicate of {canonical}: {url}")
        continue

    print(f"Fetching: {url}")

    try:
        html = fetch(url)
        parser = LinkExtractor()
        parser.feed(html)
        for href in parser.hrefs:
            full = normalize(urljoin(url, href))
            if not full.startswith(SITE):
                continue
            path = urlparse(full).path
            if any(path.endswith(suffix) for suffix in SKIP_SUFFIXES):
                continue
            if allowed(full) and full not in visited:
                to_visit.append(full)

        md = fetch(f"https://r.jina.ai/{url}")
        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"<!-- Source: {canonical} -->\n\n")
            f.write(md)
        saved_files.add(filename)
        downloaded += 1
        time.sleep(0.5)
    except Exception as exc:  # noqa: BLE001 - crawl should keep going
        failed.append((url, str(exc)))
        print(f"Failed {url}: {exc}")

# Remove stale duplicate left over from older crawls.
stale = os.path.join(OUTPUT_DIR, "liveapi_guides_v4.md")
if os.path.exists(stale) and "liveapi_guides_v4_index.html.md" in saved_files:
    os.remove(stale)
    print(f"Removed stale duplicate: {stale}")

print(f"\nDone! Downloaded {downloaded} pages into '{OUTPUT_DIR}/'.")
if failed:
    print(f"Failed ({len(failed)}):")
    for url, err in failed:
        print(f"  {url}: {err}")
