import os
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

BASE_URL = "https://the-odds-api.com/liveapi/guides/v4/"
ALLOWED_PREFIX = "https://the-odds-api.com/liveapi/"
OUTPUT_DIR = "docs_markdown"

visited = set()
to_visit = [BASE_URL]

os.makedirs(OUTPUT_DIR, exist_ok=True)

def clean_filename(url):
    path = urlparse(url).path.strip("/").replace("/", "_")
    return path if path else "index"

print("Starting docs crawl...")

while to_visit:
    url = to_visit.pop(0)
    # Normalize URL (remove query params & anchors)
    url = url.split("#")[0].split("?")[0]

    if url in visited or not url.startswith(ALLOWED_PREFIX):
        continue

    visited.add(url)
    print(f"Fetching: {url}")

    try:
        # 1. Fetch HTML to discover child links
        resp = requests.get(url, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        for a in soup.find_all("a", href=True):
            full_link = urljoin(url, a["href"]).split("#")[0].split("?")[0]
            if full_link.startswith(ALLOWED_PREFIX) and full_link not in visited:
                to_visit.append(full_link)

        # 2. Fetch clean Markdown via Jina Reader
        jina_url = f"https://r.jina.ai/{url}"
        md_resp = requests.get(jina_url, timeout=10)

        filename = f"{clean_filename(url)}.md"
        filepath = os.path.join(OUTPUT_DIR, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"<!-- Source: {url} -->\n\n")
            f.write(md_resp.text)

        time.sleep(0.5)  # Friendly rate-limiting

    except Exception as e:
        print(f"Failed {url}: {e}")

print(f"\nDone! Downloaded {len(visited)} pages into '{OUTPUT_DIR}/'.")
