from dataclasses import dataclass
import logging


COLORS = {
    "DEBUG": "\033[36m",  # cyan
    "INFO": "\033[32m",  # green
    "WARNING": "\033[33m",  # yellow
    "ERROR": "\033[31m",  # red
    "CRITICAL": "\033[1;31m",  # bold red
}
COLOR_RESET = "\033[0m"


class ColorFormatter(logging.Formatter):
    def format(self, record):
        color = COLORS.get(record.levelname, "")
        record.levelname = f"{color}{record.levelname}{COLOR_RESET}"
        return super().format(record)


def setup_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(ColorFormatter("%(levelname)s %(message)s"))
    logging.root.addHandler(handler)
    logging.root.setLevel(logging.INFO)


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
