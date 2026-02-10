#!python3


import argparse


def metadata_url(offset: int):
    return f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrnamespace=6&gsrlimit=500&gsrsearch=%22ISO%207000%20-%20Ref-No%22&&prop=imageinfo&gsroffset={offset}&iiprop=size|mime|url|user|userid"


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
