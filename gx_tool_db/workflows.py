import os
from typing import NamedTuple, Set

from gxformat2.normalize import steps_normalized

from .io import repository_walk, warn


class ToolVersionTuple(NamedTuple):
    tool_id: str
    tool_version: str


def parse_tool_ids(path: str) -> Set[str]:
    all_tools: Set[ToolVersionTuple] = parse_tools(path)
    all_tool_ids: Set[str] = set()
    for (tool_id, _) in all_tools:
        all_tool_ids.add(tool_id)
    return all_tool_ids


def parse_tools(path: str) -> Set[ToolVersionTuple]:
    all_tools: Set[ToolVersionTuple] = set()
    if os.path.isdir(path):
        for potential_workflow_file in _walk_potential_workflow_files(path):
            try:
                tool_ids = _parse_tools_from_file(potential_workflow_file)
                all_tools.update(tool_ids)
            except Exception:
                continue
    else:
        all_tools.update(_parse_tools_from_file(path))
    return all_tools


def _parse_tools_from_file(path: str) -> Set[ToolVersionTuple]:
    try:
        steps = steps_normalized(workflow_path=path)
    except Exception:
        warn(f"Problem parsing workflow file {path}")
        raise

    tools: Set[ToolVersionTuple] = set()

    def collect_from_steps(steps):
        for step in steps:
            step_type = step.get("type") or "tool"
            if (step_type not in ["tool"]) and ("run" not in step):
                continue
            tool_id = step.get("tool_id")
            tool_version = step.get("tool_version")
            if tool_id:
                tools.add(ToolVersionTuple(tool_id, tool_version))
            else:
                run = step.get("run")
                collect_from_steps(run.get("steps"))

    collect_from_steps(steps)
    return tools


def _walk_potential_workflow_files(path: str):
    for (dirpath, _, filenames) in repository_walk(path, extensions=[".yml", ".yaml", ".ga"]):
        for filename in filenames:
            # ignore some common training material / ephemeris files that aren't workflows...
            if filename in ["data-library.yaml", "data-manager.yaml", "tools.yaml"]:
                continue
            if "test." in filename or "tests." in filename:
                # probably a Galaxy test.
                continue
            yield os.path.join(dirpath, filename)
