#!python3
import argparse
import gzip
import json
import logging
import re
import time
import urllib.request
from pathlib import Path
from pprint import pprint
from typing import Dict, Iterable, List

from utils import get_svg_name, Symbol
from tqdm import tqdm

from utils import setup_logging

SOURCES = Path("sources/").resolve()
CACHE_WIKIMEDIA = SOURCES / "wikimedia.json.gz"
CACHE_SVG = SOURCES / "raw"
PROCESSED_SVG = Path("src") / "icons"


def get_wikimedia():
    """
    Download all matching metadata from wikimedia using the paginated JSON query URL in _wikimedia_url. (Sample return in example_wikimedia.json)

    <>.continue.gsroffset contains the next offset.

    Process <>.query.pages into a list and write them all to CACHE_WIKIMEDIA for later processing.
    """
    if CACHE_WIKIMEDIA.exists():
        with gzip.open(CACHE_WIKIMEDIA, "rt", encoding="utf-8") as f:
            return json.load(f)

    all_pages = []
    offset = 0

    def _wikimedia_url(offset: int = 0):
        return f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrnamespace=6&gsrlimit=50&gsrsearch=%22ISO%207000%20-%20Ref-No%22&&prop=imageinfo&gsroffset={offset}&iiprop=size|mime|url|user|userid|extmetadata&format=json"

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

        time.sleep(0.2)
    pbar.close()

    # Write all collected pages to the cache file
    with gzip.open(CACHE_WIKIMEDIA, "wt", encoding="utf-8") as f:
        json.dump(all_pages, f, indent=2, ensure_ascii=False)

    return all_pages


def process_wikimedia(wiki_data) -> List[Symbol]:
    """From each page, construct a dict with reference, title, user, url, license, description, etc.

    Log DEBUG if mime is not "image/svg+xml" or if the reference does not match the expected pattern.
    """
    skipped = 0
    ref_pattern = re.compile(r"^ISO 7000 - Ref-No (\d+[A-Z]?)$")
    symbols: Dict[str, Symbol] = {}

    for page in wiki_data:
        info = page["imageinfo"][0]
        extmeta = info["extmetadata"]

        if info["mime"] != "image/svg+xml":
            logging.debug(
                "Page %s has unexpected mime type: %s", page["title"], info["mime"]
            )
            skipped += 1
            continue

        obj_name = extmeta["ObjectName"]["value"]
        m = ref_pattern.match(obj_name)
        if not m:
            logging.debug(
                "Page %s has unexpected ObjectName: %s", page["title"], obj_name
            )
            skipped += 1
            continue

        ref = m.group(1).strip()

        new = Symbol(
            reference=ref,
            title=page["title"],
            user=info["user"],
            userid=info["userid"],
            url=info["url"],
            license=extmeta["LicenseShortName"]["value"],
            license_url=extmeta.get("LicenseUrl", {}).get("value", ""),
            description=extmeta["ImageDescription"]["value"],
            description_url=info["descriptionurl"],
        )

        if ref in symbols and symbols[ref] != new:
            logging.warning(f"Symbol {ref} duplicately defined.")
            pprint(new)
            pprint(symbols[ref])

        symbols[ref] = new

    if skipped:
        logging.info(f"Skipped {skipped} pages for incorrect name or type.")

    return sorted(symbols.values(), key=lambda s: s.reference)


def download_svgs(symbols: Iterable[Symbol]):
    """Download the SVGs if they don't already exist in CACHE_SVG"""
    CACHE_SVG.mkdir(parents=True, exist_ok=True)

    def get_svg_path(s: Symbol):
        return CACHE_SVG / get_svg_name(s)

    to_download = [
        (s, get_svg_path(s)) for s in symbols if not get_svg_path(s).exists()
    ]

    if not to_download:
        logging.info("All SVGs already downloaded.")
        return

    for symbol, path in tqdm(to_download, desc="Downloading SVGs", unit=" files"):
        req = urllib.request.Request(
            symbol.url,
            headers={
                "User-Agent": "typst-iso-7000/1.0 (https://github.com/gauravmm/typst-iso-7000)"
            },
        )
        with urllib.request.urlopen(req) as response:
            path.write_bytes(response.read())
        time.sleep(5)  # Limit set by Wikipedia


def process_svg(symbol: Symbol, force_process: bool = False):
    name = get_svg_name(symbol)
    if not force_process and (PROCESSED_SVG / name).exists():
        return
    if not (CACHE_SVG / name).exists():
        logging.debug(f"Skipped {name} as the SVG file is not downloaded.")
        return

    PROCESSED_SVG.mkdir(parents=True, exist_ok=True)
    simplify_svg(CACHE_SVG / name, PROCESSED_SVG / name)


def main(args):
    # Ensure dirs exist.
    wiki_data = get_wikimedia()
    symbols = process_wikimedia(wiki_data)
    # download_svgs(symbols.values())

    for s in tqdm(symbols, desc="Processing SVGs", unit=" files"):
        process_svg(s, args.force_process)

    # Produce output for the reference document:

    print(f"Wikimedia Entries Loaded: {len(symbols)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Scrape Wikimedia for ISO 7000 icons and generate a Typst library."
    )
    parser.add_argument(
        "--force-process",
        action="store_true",
        help="Repeat the SVG processing",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    setup_logging()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    main(args)
