#!python3
import argparse
import gzip
import json
import logging
import re
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from pprint import pprint
from typing import Dict, Iterable, List

from lxml import etree
from tqdm import tqdm

from utils import setup_logging

SOURCES = Path("sources/").resolve()
CACHE_WIKIMEDIA = SOURCES / "wikimedia.json.gz"
CACHE_SVG = SOURCES / "raw"
PROCESSED_SVG = SOURCES / "processed"


def get_svg_name(symbol: Symbol) -> str:
    return f"{symbol.reference}.svg"


@dataclass(frozen=True)
class Symbol:
    reference: str
    title: str
    user: str
    userid: int
    url: str
    license: str
    license_url: str
    description: str
    description_url: str

    def __post_init__(self):
        if not self.reference:
            raise ValueError(f"Symbol reference must not be empty (title={self.title})")


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

    # Remove <{g|path} stroke="#999999"... /> and its descendants

    tree = etree.parse(str(CACHE_SVG / name))
    # Strip out all comments
    etree.strip_elements(tree, etree.Comment, with_tail=False)

    root = tree.getroot()

    # Remove all elements and attributes with non-svg namespaces
    for elem in root.xpath(".|.//*"):
        # QName(elem).namespace returns the URI
        if etree.QName(elem).namespace != "http://www.w3.org/2000/svg" or etree.QName(
            elem
        ).localname in ("defs",):
            parent = elem.getparent()
            if parent is not None:
                parent.remove(elem)
            continue

        for attr_name in list(elem.attrib.keys()):
            if "}" in attr_name:  # Namespaced attribute
                del elem.attrib[attr_name]

    # Clean up unused namespace declarations
    etree.cleanup_namespaces(tree)

    # Remove gray stroke elements using XPath
    # Remove <defs> elements
    for elem in root.xpath(".//defs"):
        elem.getparent().remove(elem)

    # Remove <g> and <path> elements with gray strokes (#999 or #999999)
    for elem_type in ("g", "path"):
        for elem in root.xpath(
            f".//*[local-name()='{elem_type}'][contains(@stroke, '#999')]"
        ):
            elem.getparent().remove(elem)

        # Remove <g> and <path> elements with #999 in style attribute
        for elem in root.xpath(
            f".//*[local-name()='{elem_type}'][contains(@style, '#999')]"
        ):
            elem.getparent().remove(elem)

    # Repeatedly remove orphan <g> elements (groups with no element children)
    while True:
        # Find all <g> elements with no child elements (only text/whitespace allowed)
        orphans = root.xpath(".//*[local-name()='g'][not(*)]")
        if not orphans:
            break
        for elem in orphans:
            parent = elem.getparent()
            if parent is not None:
                parent.remove(elem)

    # Handle viewBox and root size (width/height)
    width = root.get("width")
    height = root.get("height")
    viewBox = root.get("viewBox")

    if not (width and height):
        if not viewBox:
            # Case 4: neither is set → report error and set defaults
            logging.error(
                f"{name}: Neither viewBox nor size attributes found, skipping..."
            )
            return
    # Case 1: viewBox set, but not root size → set root size to 10mm x 10mm
    elif not viewBox:
        # Case 2: root size set, but not viewBox → set viewBox
        try:
            # Parse numeric values from width/height (strip units like px, mm, etc.)
            root.set("viewBox", f"0 0 {float(width)} {float(height)}")
        except ValueError:
            logging.error(
                f"{name}: Could not parse width/height ({width}, {height}), skipping..."
            )
            return
    # Case 3: both are set → keep viewBox, set size to 10mm

    root.set("width", "10mm")
    root.set("height", "10mm")

    PROCESSED_SVG.mkdir(parents=True, exist_ok=True)
    tree.write(
        str(PROCESSED_SVG / name),
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True,
    )


def main(args):
    # Ensure dirs exist.
    wiki_data = get_wikimedia()
    symbols = process_wikimedia(wiki_data)
    # download_svgs(symbols.values())

    for s in tqdm(symbols, desc="Processing SVGs", unit=" files"):
        process_svg(s, args.force_process)

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
