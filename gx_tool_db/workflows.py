import os
from typing import Set

from gxformat2.normalize import steps_normalized

from .io import warn


def parse_tool_ids(path: str) -> Set[str]:
    if os.path.isdir(path):
        all_tool_ids = set()
        for potential_workflow_file in _walk_potential_workflow_files(path):
            try:
                tool_ids = _parse_tool_ids_from_file(potential_workflow_file)
                all_tool_ids.update(tool_ids)
            except Exception:
                continue
        return all_tool_ids
    else:
        return _parse_tool_ids_from_file(path)


def _parse_tool_ids_from_file(path: str) -> Set[str]:
    try:
        steps = steps_normalized(workflow_path=path)
    except Exception:
        warn(f"Problem parsing workflow file {path}")
        raise

    tool_ids = set()
    for step in steps:
        step_type = step.get("type") or "tool"
        if step_type != "tool":
            continue  # TODO: subworkflows...
        tool_id = step.get("tool_id")
        tool_ids.add(tool_id)
    return tool_ids


def _walk_potential_workflow_files(path: str):
    for (dirpath, _, filenames) in os.walk(path):
        for filename in filenames:
            if os.path.splitext(filename)[1] in [".yml", ".yaml", ".ga"]:
                yield os.path.join(dirpath, filename)
