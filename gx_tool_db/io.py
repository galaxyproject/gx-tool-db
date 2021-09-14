import contextlib
import csv
import io
import os
from typing import Any, Dict

import urllib3


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


def repository_walk(path, extensions=None):
    """Variant of os.walk that skips hidden files."""
    for (dirpath, dirs, filenames) in os.walk(path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        filenames[:] = [f for f in filenames if not f.startswith(".")]
        if extensions is not None:
            filenames[:] = [f for f in filenames if any(f.endswith(e) for e in extensions)]
        yield (dirpath, dirs, filenames)


def open_uri(input_path_or_uri: str):
    if "://" not in input_path_or_uri:
        return open(input_path_or_uri, "r")
    else:
        http = urllib3.PoolManager()
        r = http.request('GET', input_path_or_uri, preload_content=False)
        r.auto_close = False
        return io.TextIOWrapper(r)
