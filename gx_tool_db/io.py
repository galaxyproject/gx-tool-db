import contextlib
import csv
from typing import Any, Dict


def warn(message):
    print(f"WARNING: {message}")


@contextlib.contextmanager
def csv_writer(path: str):
    """CSV writer that uses path extension to infer how to write CSV."""
    csv_kwds = _path_to_csv_args(path)
    with open(path, "w") as f:
        writer = csv.writer(f, **csv_kwds)
        yield writer


@contextlib.contextmanager
def csv_reader(path: str):
    """CSV reader that uses path extension to infer how to reader CSV."""
    csv_kwds = _path_to_csv_args(path)
    with open(path, "r") as f:
        reader = csv.reader(f, **csv_kwds)
        yield reader


@contextlib.contextmanager
def csv_dict_reader(path: str):
    """CSV DictReader that uses path extension to infer how to reader CSV."""
    csv_kwds = _path_to_csv_args(path)
    with open(path, "r") as f:
        reader = csv.DictReader(f, **csv_kwds)
        yield reader


def _path_to_csv_args(path: str) -> Dict[str, Any]:
    csv_kwds = {}
    if not path.endswith("csv"):
        csv_kwds = dict(delimiter="\t", quotechar='"')
    return csv_kwds
