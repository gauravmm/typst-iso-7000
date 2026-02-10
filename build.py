#!python3

import argparse
import json
import time
import urllib.request
from pathlib import Path

from tqdm import tqdm

SOURCES = Path("sources/").resolve()
CACHE_WIKIMEDIA = SOURCES / "wikimedia.json"


def get_wikimedia():
    """
    Download all matching metadata from wikimedia using the paginated JSON query URL in _wikimedia_url. (Sample return in example_wikimedia.json)

    <>.continue.gsroffset contains the next offset.

    Process <>.query.pages into a list and write them all to CACHE_WIKIMEDIA for later processing.
    """
    if CACHE_WIKIMEDIA.exists():
        return json.loads(CACHE_WIKIMEDIA.read_text())

    all_pages = []
    offset = 0

    def _wikimedia_url(offset: int = 0):
        return f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrnamespace=6&gsrlimit=50&gsrsearch=%22ISO%207000%20-%20Ref-No%22&&prop=imageinfo&gsroffset={offset}&iiprop=size|mime|url|user|userid&format=json"

    pbar = tqdm(desc="Fetching Wikimedia metadata", unit=" pages")
    while True:
        # Fetch data from Wikimedia API
        url = _wikimedia_url(offset)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "typst-iso-7000/1.0 (https://github.com/gauravmm/typst-iso-7000)"
            },
        )
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))

        # Extract pages from the response and add to our list
        if "query" in data and "pages" in data["query"]:
            pages = data["query"]["pages"]
            all_pages.extend(pages.values())
            pbar.update(len(pages))

        # Check if there are more results to fetch
        if "continue" in data and "gsroffset" in data["continue"]:
            offset = data["continue"]["gsroffset"]
        else:
            break

        time.sleep(0.5)
    pbar.close()

    # Write all collected pages to the cache file
    with open(CACHE_WIKIMEDIA, "w", encoding="utf-8") as f:
        json.dump(all_pages, f, indent=2, ensure_ascii=False)

    return all_pages


def main(args):
    # Ensure dirs exist.
    # CACHE_WIKIMEDIA.parent.mkdir(parents=True, exist_ok=True)
    wiki_data = get_wikimedia()

    print(f"Wikimedia Entries Loaded: {len(wiki_data)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scrape Wikimedia for ISO 7000 icons and generate a Typst library."
    )
    parser.add_argument(
        "--force-search-again",
        action="store_true",
        help="Repeat the Wikimedia search to check if new documents are available.",
    )
    main(parser.parse_args())
