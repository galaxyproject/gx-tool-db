"""Models only used for validation so far.

Might be better as the core for calculation and could serve as nice documentation
of the data model as well.
"""
import os
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Extra
from typing_extensions import Literal

from .config import DEFAULT_DATABASE_PATH, TestDataMergeStrategy


class GxToolDbBaseModel(BaseModel, extra=Extra.forbid):  # type: ignore
    pass


class Section(GxToolDbBaseModel):
    name: str


class ServerToolMetadata(GxToolDbBaseModel):
    versions: Optional[List[str]]
    sections: Optional[Dict[str, Section]]


class ServerToolVersionMetadata(GxToolDbBaseModel):
    labels: Optional[List[str]]


class TestResult(GxToolDbBaseModel):
    status: str
    job_create_time: Optional[str]

    @property
    def successful(self):
        return self.status == "success"

    def best(self, other):
        self_successful = self.successful
        other_successful = other.successful

        if self_successful != other_successful:
            return self if self_successful else other

        self_has_metadata = self.job_create_time is not None
        other_has_metadata = other.job_create_time is not None
        if self_has_metadata != other_has_metadata:
            return self if self_has_metadata else other

        if self_has_metadata:
            if self.job_create_time < other.job_create_time:
                return other
            else:
                return self
        else:
            # neither have metadata, go with the second since added more recently...
            return other


class TestResults(GxToolDbBaseModel):
    __root__: Dict[int, TestResult]

    @staticmethod
    def from_test_output_dicts(version_results: List[dict]):
        cleaned_results = {}
        for result in version_results:
            cleaned_result = {}
            test_index = result.get("test_index")
            for key in ["status"]:
                if key in result:
                    cleaned_result[key] = result.get(key)
            job = result.get("job", {})
            for job_key in ["create_time"]:
                if job_key in job:
                    cleaned_result[f"job_{job_key}"] = job.get(job_key)

            cleaned_results[test_index] = cleaned_result

        return TestResults(__root__=cleaned_results)

    def _best_metrics(self):
        tests = 0
        successful = 0
        has_metadata = 0
        for test_result in self.__root__.values():
            tests += 1
            if test_result.successful:
                successful += 1
            if test_result.job_create_time is not None:
                has_metadata += 1
        return [successful, tests, has_metadata]

    def best(self, other: 'TestResults'):
        # return the 'best' TestResults
        self_metrics = self._best_metrics()
        other_metrics = other._best_metrics()
        for self_metric, other_metric in zip(self_metrics, other_metrics):
            if self_metric == other_metric:
                continue
            if self_metric > other_metric:
                return self
            else:
                return other
        return other

    def merged(self, other: 'TestResults', strategy: TestDataMergeStrategy):
        """Merge this existing data with 'newer' data (other)."""
        if strategy == TestDataMergeStrategy.latest_added:
            return other
        elif strategy == TestDataMergeStrategy.latest_executed:
            when_executed = self.when_executed
            other_when_executed = other.when_executed
            if other_when_executed is None:
                return self
            elif when_executed is None:
                return other
            elif when_executed < other_when_executed:
                return other
            else:
                return self
        elif strategy == TestDataMergeStrategy.best:
            return self.best(other)
        else:
            # index wise...
            all_indicies = list(sorted(set(self.__root__.keys()).union(other.__root__.keys())))

            new_root = {}
            for index in all_indicies:
                index_result = None
                if not self.has_index(index):
                    index_result = other.__root__[index]
                elif not other.has_index(index):
                    index_result = self.__root__[index]
                else:
                    self_index_result = self.__root__[index]
                    other_index_result = other.__root__[index]
                    if strategy == TestDataMergeStrategy.latest_added_indexwise:
                        index_result = other_index_result
                    elif strategy == TestDataMergeStrategy.latest_executed_indexwise:
                        when_executed_index = self_index_result.job_create_time
                        other_when_executed_index = other_index_result.job_create_time
                        if other_when_executed_index is None:
                            index_result = self_index_result
                        elif when_executed_index is None:
                            index_result = other_index_result
                        elif when_executed_index < other_when_executed_index:
                            index_result = other_index_result
                        else:
                            index_result = self_index_result
                    else:
                        index_result = self_index_result.best(other_index_result)
                assert index_result is not None
                new_root[index] = index_result.dict()
            return TestResults(__root__=new_root)

        return other

    def has_index(self, test_index):
        return test_index in self.__root__

    @property
    def when_executed(self):
        for test_result in self.__root__.values():
            created = test_result.job_create_time
            if created:
                return created
        return None


class TrainingMetadata(GxToolDbBaseModel):
    topic: str
    tutorial: str

    def __hash__(self):
        return hash((type(self),) + tuple(self.__dict__.values()))


class ToolVersionMetadata(GxToolDbBaseModel):
    test_results: Optional[Dict[str, TestResults]]
    servers: Optional[Dict[str, ServerToolVersionMetadata]]
    trainings: Optional[List[TrainingMetadata]]


class ToolShedRepostiry(GxToolDbBaseModel):
    owner: str
    tool_shed: str
    name: str


class ToolMetadata(GxToolDbBaseModel):
    servers: Optional[Dict[str, ServerToolMetadata]]
    versions: Optional[Dict[str, ToolVersionMetadata]]
    external_labels: Optional[List[str]]
    tool_shed_repository: Optional[ToolShedRepostiry]


class ToolSectionLabel(GxToolDbBaseModel):
    model_class: Literal['ToolSectionLabel']
    id: str
    text: str


class ToolSection(GxToolDbBaseModel):
    model_class: Literal['ToolSection']
    id: str
    name: str


IntegratedPanelSkeletonItems = Union[
    ToolSectionLabel,
    ToolSection,
]


class ToolPanelSkeleton(GxToolDbBaseModel):
    __root__: List[IntegratedPanelSkeletonItems]


class ToolDatabase(GxToolDbBaseModel):
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
