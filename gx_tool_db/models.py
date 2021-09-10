"""Models only used for validation so far.

Might be better as the core for calculation and could serve as nice documentation
of the data model as well.
"""
import os
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel
from typing_extensions import Literal

from .config import DEFAULT_DATABASE_PATH


class ServerToolMetadata(BaseModel):
    pass


class TestResult(BaseModel):
    status: str
    job_create_time: Optional[str]


class TestResults(BaseModel):
    __root__: Dict[int, TestResult]


class ToolVersionMetadata(BaseModel):
    test_results: Optional[Dict[str, TestResults]]


class ToolMetadata(BaseModel):
    servers: Optional[Dict[str, ServerToolMetadata]]
    versions: Optional[Dict[str, ToolVersionMetadata]]
    latest_version: Optional[str]
    external_labels: Optional[List[str]]


class ToolSectionLabel(BaseModel):
    model_class: Literal['ToolSectionLabel']
    id: str
    text: str


class ToolSection(BaseModel):
    model_class: Literal['ToolSection']
    id: str
    name: str


IntegratedPanelSkeletonItems = Union[
    ToolSectionLabel,
    ToolSection,
]


class ToolPanelSkeleton(BaseModel):
    __root__: List[IntegratedPanelSkeletonItems]


class ToolDatabase(BaseModel):
    version: Literal['1.0']
    tools: Optional[Dict[str, ToolMetadata]]
    integrated_panels: Optional[Dict[str, ToolPanelSkeleton]]


def load_from_path(path: str = ".") -> ToolDatabase:
    """Load Pydantic model form of the database.

    Supplied `path` can be a directory containing tools_metadata.yml or an actual YAML file.
    """
    if os.path.isdir(path):
        path = os.path.join(path, DEFAULT_DATABASE_PATH)
    with open(path, "r") as f:
        as_dict = yaml.safe_load(f)
    return ToolDatabase(**as_dict)


def load_from_dict(as_dict: Dict[str, Any]) -> ToolDatabase:
    """Load Pydantic model form of the database."""
    return ToolDatabase(**as_dict)


def validate(path: str) -> None:
    """Validate the YAML database at the specified path using Pydantic models.

    Supplied `path` can be a directory containing tools_metadata.yml or an actual YAML file.
    """
    load_from_path(path)
