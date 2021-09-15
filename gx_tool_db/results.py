"""Abstractions for test result data."""
import json
import os
from typing import Iterator, NamedTuple

from gx_tool_db.io import open_uri, repository_walk


class TestResults:
    """Abstraction around the contents of test output JSON file."""

    def __init__(self, path=None, json_contents=None):
        results = {}
        if path is not None:
            with open_uri(path) as f:
                results = json.load(f)
        else:
            assert json_contents is not None
            results = json_contents

        tests = results["tests"]

        results_by_id = {}
        for result in tests:
            if not result.get("has_data"):
                continue
            result_data = result.get("data")
            tool_id = result_data['tool_id']
            if tool_id not in results_by_id:
                results_by_id[tool_id] = []
            results_by_id[tool_id].append(result_data)
        self.results_by_id = results_by_id

    def get_results_for_tool_id(self, tool_id):
        results_by_id = self.results_by_id
        if tool_id in results_by_id:
            return results_by_id[tool_id]
        else:
            tool_id = tool_id.rsplit("/", 1)[0]
            return results_by_id.get(tool_id)


class TestResultsCollection(NamedTuple):
    """TestResults along with its source."""
    uri: str
    results: TestResults


def result_collections(uri: str) -> Iterator[TestResultsCollection]:
    if "://" in uri or not os.path.isdir(uri):
        yield TestResultsCollection(uri, TestResults(path=uri))
    else:
        yield from _walk_potential_result_files(uri)


def _walk_potential_result_files(path: str):
    for (dirpath, _, filenames) in repository_walk(path, extensions=[".json"]):
        for filename in filenames:
            json_path = os.path.join(dirpath, filename)
            with open(json_path, "r") as f:
                results = json.load(f)
                if "tests" in results:
                    yield TestResultsCollection(
                        json_path,
                        TestResults(json_contents=results)
                    )
