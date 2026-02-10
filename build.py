#!python3


import argparse
from pathlib import Path

CACHE_WIKIMEDIA = Path("sources/wikimedia.json")


def get_wikimedia():
    """
    Download all matching metadata from wikimedia using the paginated JSON query URL in _wikimedia_url. (Sample return in example_wikimedia.json)

    <>.continue.gsroffset contains the next offset.

    Process <>.query.pages into a list and write them all to CACHE_WIKIMEDIA for later processing.
    """
    pass


def _wikimedia_url(offset: int):
    return f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrnamespace=6&gsrlimit=50&gsrsearch=%22ISO%207000%20-%20Ref-No%22&&prop=imageinfo&gsroffset={offset}&iiprop=size|mime|url|user|userid&format=json"


def main(args):
    pass


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
