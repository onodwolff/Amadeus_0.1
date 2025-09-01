import logging
from logging.handlers import RotatingFileHandler

def setup_logging(path: str = "bot.log", level=logging.INFO, to_console: bool = True):
    root = logging.getLogger()
    root.setLevel(level)
    for h in list(root.handlers):
        root.removeHandler(h)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    fh = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    fh.setLevel(level); fh.setFormatter(fmt); root.addHandler(fh)

    if to_console:
        ch = logging.StreamHandler()
        ch.setLevel(level); ch.setFormatter(fmt); root.addHandler(ch)

    return root
