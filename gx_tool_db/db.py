import os
import shutil
import tempfile
from typing import Any, Dict, Iterator, List, Optional, Set

import packaging.version
import yaml

from .config import FilterArguments, Server, TestDataMergeStrategy, ViewDefintion
from .io import warn
from .models import load_from_dict, TestResults, TrainingMetadata
from .workflows import parse_tools

DATABASE_VERSION = "1.0"


class FilterCriteria:
    require_repository: Optional[bool] = None
    require_main_shed: Optional[bool] = None
    require_labels: Optional[List[str]] = None
    exclude_labels: Optional[List[str]] = None


class ToolsMetadata:
    metadata: dict

    def __init__(self, metadata_file: str):
        self._metadata_file = metadata_file
        self._init()

    def _init(self):
        metadata = {
            'version': DATABASE_VERSION,
        }
        if os.path.exists(self._metadata_file):
            with open(self._metadata_file, 'r') as f:
                metadata = yaml.safe_load(f)
        load_from_dict(metadata)  # validate models
        self.metadata = metadata

    def get_entry_for(self, tool_id, server: Optional[Server] = None):
        """Fetch entry for parsed tool id."""
        tools_dict = self._tools_dict()
        tool_source = _ensure_key(tools_dict, tool_id, {})
        return ToolEntry(tool_source, tool_id, server)

    def get_entry_for_api_value(self, api_element, server: Optional[Server] = None):
        assert api_element["model_class"].endswith("Tool"), api_element
        raw_tool_id = api_element["id"]
        tool_id = _versionless_tool_id(raw_tool_id)
        return self.get_entry_for(tool_id, server)

    def record_panel_skeleton(self, skeleton_elements: List[Dict], server: Server):
        panels = _ensure_key(self.metadata, "integrated_panels", {})
        panels[server.label] = skeleton_elements

    def panel_skeleton_for(self, server_label: str):
        panels = _ensure_key(self.metadata, "integrated_panels", {})
        return panels.get(server_label)

    def write(self):
        load_from_dict(self.metadata)  # make sure models validate before writing...

        # TODO: backups...

        # Dump it to a temporary file and then move the file to prevent
        # truncated file problems on serialization errors, etc..
        tf = tempfile.NamedTemporaryFile('w', delete=False)
        yaml.safe_dump(self.metadata, tf)
        shutil.move(tf.name, self._metadata_file)

    def known_servers(self):
        """List of unique servers attached to tool metadata."""
        servers = set()
        for _, tool_metadata in self._tools_dict().items():
            for version in tool_metadata.get("versions", {}).values():
                for server in version["servers"].keys():
                    servers.add(server)
            for server in tool_metadata.get("servers", {}).keys():
                servers.add(server)
        return list(servers)

    def test_keys(self):
        """List of unique keys (labels) attached to available test data."""
        test_keys = set()
        for _, tool_metadata in self._tools_dict().items():
            for version in tool_metadata.get("versions", {}).values():
                test_results = version.get("test_results", {})
                test_keys.update(test_results.keys())
        return list(test_keys)

    def entries(self, server: Optional[Server] = None, filter_criteria: FilterCriteria = None) -> Iterator['ToolEntry']:
        for tool_id, tool_metadata in self.walk_tools_dict(filter_criteria):
            yield ToolEntry(tool_metadata, tool_id, server)

    def clear_test_results(self, test_target):
        for _, tool_metadata in self._tools_dict().items():
            for version in tool_metadata.get("versions", {}).values():
                test_results = version.get("test_results", {})
                test_results.pop(test_target, None)
                if not test_results:
                    version.pop("test_results", None)

    def clear_label(self, label_key):
        for _, tool_metadata in self._tools_dict().items():
            external_labels = tool_metadata.get("external_labels", {})
            external_labels.pop(label_key, None)
            if not external_labels:
                tool_metadata.pop("external_labels", None)

    def _tools_dict(self):
        return _ensure_key(self.metadata, "tools", {})

    def _panels_dict(self):
        return _ensure_key(self.metadata, "panels", {})

    def walk_tools_dict(self, filter_criteria: Optional[FilterCriteria] = None):
        filter_criteria = filter_criteria or FilterCriteria()
        for tool_id, tool_metadata in self._tools_dict().items():
            repo_dict = tool_metadata.get("tool_shed_repository", None)

            if filter_criteria.require_repository and repo_dict is None:
                continue

            tool_shed = (repo_dict or {}).get("tool_shed")
            if filter_criteria.require_main_shed and tool_shed != "toolshed.g2.bx.psu.edu":
                continue

            external_labels = tool_metadata.get("external_labels", [])
            filter_based_on_labels = False

            if filter_criteria.require_labels:
                for required_label in filter_criteria.require_labels:
                    if required_label not in external_labels:
                        filter_based_on_labels = True
                        break

            for exclude_label in (filter_criteria.exclude_labels or []):
                if exclude_label in external_labels:
                    filter_based_on_labels = True
                    break

            if filter_based_on_labels:
                continue

            yield tool_id, tool_metadata

    def install_dict(self, servers: Optional[List[str]], filter_args: FilterArguments):
        """Return an install dict for Ephemeris or ansible-galaxy-tools."""
        repos = []
        repos_added = set()

        filter_criteria = FilterCriteria()
        filter_criteria.require_repository = True
        filter_criteria.require_main_shed = True
        filter_criteria.require_labels = filter_args.require_labels
        filter_criteria.exclude_labels = filter_args.exclude_labels

        for _, tool_metadata in self.walk_tools_dict(filter_criteria):
            repo_dict = tool_metadata.get("tool_shed_repository", None)

            repo_owner = repo_dict["owner"]
            repo_name = repo_dict["name"]
            repo_hash = f"{repo_owner}|||{repo_name}"
            if repo_hash in repos_added:
                continue

            server_dicts = filter_server_dicts(tool_metadata, servers)
            section_label = None
            for server_dict in server_dicts.values():
                sections = server_dict.get("sections", {})
                if len(sections) > 0:
                    section = list(sections.values())[0]
                    section_label = section["name"]
                    break

            if section_label is None:
                warn(f"Could not find section label for {repo_owner}/{repo_name} - skipping install tool entry.")
                continue

            repo = {
                "owner": repo_owner,
                "name": repo_name,
                "tool_panel_section_label": section_label,
            }
            repos.append(repo)
            repos_added.add(repo_hash)

        return {
            "tools": repos,
        }

    def panel_view_dict(self, server_label: str, view_def: ViewDefintion):
        filter_criteria = FilterCriteria()
        filter_criteria.require_labels = view_def.require_labels
        filter_criteria.exclude_labels = view_def.exclude_labels

        rval: Dict[str, Any] = {
            "id": view_def.id,
            "type": view_def.view_type,
            "name": view_def.name or view_def.id,
        }
        if view_def.description:
            rval["description"] = view_def.description

        sections_tools = self.sections_tools(server_label, filter_criteria)
        panel_skeleton = self.panel_skeleton_for(server_label)
        if panel_skeleton is None:
            raise Exception(f"No panel skeleton bootstrapped for {server_label}")

        items = []
        for panel_skeleton_item in panel_skeleton:
            model_class = panel_skeleton_item["model_class"]
            panel_skeleton_item_id = panel_skeleton_item["id"]

            if model_class == "ToolSectionLabel":
                text = panel_skeleton_item["text"]
                item = {
                    "id": panel_skeleton_item_id,
                    "text": text,
                    "type": "label",
                }
                # // or just 'label: text'. Maybe add a --concise flag.
                items.append(item)
            else:
                assert model_class == "ToolSection"
                section_id = panel_skeleton_item_id
                name = panel_skeleton_item["name"]
                section_tools = sections_tools.get(section_id)
                if not section_tools:
                    continue

                section = {
                    "id": panel_skeleton_item_id,
                    "name": name,
                    "type": "section",
                }
                # If we're requiring a label need to specify the elements, otherwise we can just
                # count on a global exclude of the tools in the map.
                if view_def.require_labels:
                    section_items = []
                    for tool_id in section_tools:
                        section_items.append({
                            "type": "tool",
                            "id": tool_id,
                        })
                    section["items"] = section_items
                items.append(section)

        rval["items"] = items

        exclude_labels = view_def.exclude_labels
        if exclude_labels:
            excluded_ids = []
            for tool_entry in self.entries():
                if tool_entry.has_server_data_for(server_label):
                    continue

                for excluded_label in exclude_labels:
                    if tool_entry.has_external_label(excluded_label):
                        excluded_ids.append(tool_entry.tool_id)
            rval["excludes"] = [
                {"tool_id": tool_id} for tool_id in excluded_ids
            ]
        return rval

    def sections_tools(self, server_label: str, filter_criteria: FilterCriteria) -> Dict[str, Set[str]]:
        sections_tools: Dict[str, Set[str]] = {}
        for tool_entry in self.entries(filter_criteria=filter_criteria):
            server_dict = tool_entry.server_dict_for(server_label)
            if server_dict is None:
                continue  # tool not found on server

            server_sections = server_dict.get("sections") or {}
            for server_section_id in server_sections.keys():
                section_tools = _ensure_key(sections_tools, server_section_id, set())
                section_tools.add(tool_entry.tool_id)
        return sections_tools

    def import_trainings(self, training_directory: str):
        topics_directory = os.path.join(training_directory, "topics")
        for topic in os.listdir(topics_directory):
            topic_directory = os.path.join(topics_directory, topic)
            tutorials_directory = os.path.join(topic_directory, "tutorials")
            if not os.path.exists(tutorials_directory):
                continue
            tutorials = os.listdir(tutorials_directory)
            for tutorial in tutorials:
                tutorial_directory = os.path.join(tutorials_directory, tutorial)
                workflow_tools = parse_tools(tutorial_directory)
                for (raw_tool_id, tool_version) in workflow_tools:
                    tool_id = _versionless_tool_id(raw_tool_id)
                    if tool_version is None and "repos" in raw_tool_id:
                        # TODO: workflow missing version - why?
                        tool_version = raw_tool_id.rsplit("/", 1)[1]

                    tool_entry = self.get_entry_for(tool_id)
                    if not tool_version:
                        warn(f"No tool_version for tool_id {tool_id} found in workflow and cannot infer from tool ID, skipping training entry")
                        continue

                    tool_version_entry = tool_entry.get_version_entry(tool_version)
                    tool_version_entry.record_training(TrainingMetadata(topic=topic, tutorial=tutorial))

    # YAGNI
    # def entries_with_label(self, label):
    #     for tool_entry in self.entries(filter_criteria=filter_criteria):
    #         if tool_entry.has_external_label(label):
    #             yield tool_entry

    # def tool_ids_for(self, server_label: str) -> List[str]:
    #     tool_ids = List[str]
    #     for tool_entry in self.entries():
    #         if tool_entry.has_server_data_for(server_label):
    #             tool_ids.append(tool_entry.tool_id)
    #     return tool_ids


def filter_server_dicts(tool_metadata, servers: Optional[List[str]] = None):
    server_dicts = tool_metadata.get("servers", {})
    if servers:
        filtered_dicts = {}
        # walk servers so we get the resulting dict in the prefered order.
        for server in servers:
            if server in server_dicts:
                filtered_dicts[server] = server_dicts[server]
        return filtered_dicts
    else:
        return server_dicts


class ToolEntry:

    def __init__(self, source_data: dict, tool_id: str, server: Optional[Server] = None):
        self._source_data = source_data
        self._tool_id = tool_id
        self._server = server
        self._server_dict()  # just to init it...

    def _server_dict(self):
        if self._server is not None:
            servers = _ensure_key(self._source_data, "servers", {})
            return _ensure_key(servers, self._server.label, {})
        return None

    def has_server_data_for(self, server_label):
        return server_label in _ensure_key(self._source_data, "servers", {})

    def server_dict_for(self, server_label: str):
        return _ensure_key(self._source_data, "servers", {}).get(server_label)

    def get_version_entry(self, version: str) -> Optional['ToolVersionEntry']:
        versions = _ensure_key(self._source_data, "versions", {})
        _ensure_key(versions, version, {})

        if len(versions) == 0:
            return None

        if self._server is not None:
            server_source = self._server_dict()
            server_versions = _ensure_key(server_source, "versions", [])
            if version not in server_versions:
                server_versions.append(version)

        return ToolVersionEntry(versions[version], self, version)

    def get_version_entries(self):
        versions_dict = _ensure_key(self._source_data, "versions", {})
        versions = _version_sorted_keys(versions_dict)
        for version in versions:
            yield self.get_version_entry(version)

    def record_ts_repo(self, repo_dict: Optional[dict]):
        if repo_dict:
            self._source_data["tool_shed_repository"] = {
                "name": repo_dict["name"],
                "owner": repo_dict["owner"],
                "tool_shed": repo_dict["tool_shed"]
            }

    def record_section(self, section_id, section_name):
        server_dict = self._server_dict()
        if server_dict is None:
            return
        sections = _ensure_key(server_dict, "sections", {})
        sections[section_id] = {"name": section_name}

    def record_external_label(self, label, present=True):
        if present:
            external_labels = _ensure_key(self._source_data, "external_labels", [])
            if label not in external_labels:
                external_labels.append(label)
        else:
            if not "external_labels" in self._source_data:
                return

            external_labels = _ensure_key(self._source_data, "external_labels", [])
            if label in external_labels:
                external_labels.remove(label)

    def has_external_label(self, label):
        if not "external_labels" in self._source_data:
            return False
        external_labels = _ensure_key(self._source_data, "external_labels", [])
        return label in external_labels

    def get_latest_test_results_dict(self) -> Dict[str, 'ToolLatestTestResults']:
        latest_test_results_dict = {}

        # for each test source label, get the latest test results dict
        for tool_version_entry in self.get_version_entries():
            test_results_by_target = tool_version_entry.get_test_results()

            for test_target, test_results in test_results_by_target.items():
                if test_target in latest_test_results_dict:
                    # already found test results for a newer version for this test target
                    continue

                tool_latest_test_results = ToolLatestTestResults()
                tool_latest_test_results.tool_version_entry = tool_version_entry
                tool_latest_test_results.test_results = test_results

                latest_test_results_dict[test_target] = tool_latest_test_results

        return latest_test_results_dict

    @property
    def tool_id(self) -> str:
        return self._tool_id

    @property
    def latest_version(self) -> Optional[str]:
        keys = _version_sorted_keys(self._source_data.get("versions", {}))
        return keys[0] if keys else None

    @property
    def trainings(self) -> Set[TrainingMetadata]:
        trainings: Set[TrainingMetadata] = set()
        for version in self.get_version_entries():
            trainings.update(version.trainings)
        return trainings

    @property
    def training_topics(self) -> Set[str]:
        topics: Set[str] = set()
        for training in self.trainings:
            topics.add(training.topic)
        return topics

    @property
    def name(self) -> Optional[str]:
        return self._newest_version_with_metadata("name")

    @property
    def description(self) -> Optional[str]:
        return self._newest_version_with_metadata("description")

    @property
    def model_class(self) -> Optional[str]:
        return self._newest_version_with_metadata("model_class")

    @property
    def tool_shed(self) -> Optional[str]:
        return self._tool_shed_prop("tool_shed")

    @property
    def repository_name(self) -> Optional[str]:
        return self._tool_shed_prop("name")

    @property
    def repository_owner(self) -> Optional[str]:
        return self._tool_shed_prop("owner")

    def _tool_shed_prop(self, key: str) -> Optional[str]:
        repo_dict = self._source_data.get("tool_shed_repository")
        if repo_dict:
            return repo_dict.get(key)
        return None

    def _newest_version_with_metadata(self, key):
        for tool_version_entry in self.get_version_entries():
            value = tool_version_entry._source_data.get(key)
            if value:
                return value
        return None


class ToolVersionEntry:

    def __init__(self, source_data: dict, tool_entry: ToolEntry, version: str):
        self._source_data = source_data
        self._tool_entry = tool_entry
        self._version = version

    @property
    def tool_version(self) -> str:
        return self._version

    @property
    def _server(self):
        return self._tool_entry._server

    def _server_dict(self):
        server = self._server
        if server:
            servers = _ensure_key(self._source_data, "servers", {})
            return _ensure_key(servers, self._server.label, {})
        else:
            return None

    def record_labels(self, labels):
        server_dict = self._server_dict()
        if server_dict is not None:
            server_dict["labels"] = labels

    def record_training(self, training: TrainingMetadata):
        trainings = _ensure_key(self._source_data, "trainings", [])
        trainings.append(training.dict())

    @property
    def trainings(self):
        trainings: Set[TrainingMetadata] = set()
        raw_trainings = _ensure_key(self._source_data, "trainings", [])
        for raw_training in raw_trainings:
            trainings.add(TrainingMetadata(**raw_training))
        return trainings

    def record_test_results(self, test_target, test_results: TestResults, merge_strategy: TestDataMergeStrategy):
        results = self.get_test_results()
        target_results = results.get(test_target)
        if not target_results:
            # just set them, no need to worry about how to replace...
            results[test_target] = test_results.dict()["__root__"]
        else:
            # ideally we should compare and choose...
            old_test_results = TestResults(__root__=target_results)
            merged_test_results = old_test_results.merged(test_results, merge_strategy)
            results[test_target] = merged_test_results.dict()["__root__"]

    def get_test_results_for(self, test_target) -> Dict:
        results = self.get_test_results()
        target_results = _ensure_key(results, test_target, {})
        return target_results

    def get_test_results(self):
        results = _ensure_key(self._source_data, "test_results", {})
        return results

    def record_metadata(
        self,
        name: str,
        description: Optional[str] = None,
        xrefs: Optional[List[str]] = None,
        edam_operations: Optional[List[str]] = None,
        edam_topics: Optional[List[str]] = None,
        model_class: Optional[str] = None,
    ):
        data = self._source_data
        data["name"] = name
        if description:
            data["description"] = description
        if xrefs:
            data["xrefs"] = xrefs
        if edam_operations:
            data["edam_operations"] = edam_operations
        if edam_topics:
            data["edam_topics"] = edam_topics
        if model_class:
            data["model_class"] = model_class


class ToolLatestTestResults:
    tool_version_entry: ToolVersionEntry
    test_results: dict


def _ensure_key(the_dict: dict, key: str, the_default: Any):
    if key not in the_dict:
        the_dict[key] = the_default
    return the_dict[key]


def _id_to_version(tool_id):
    if 'repos' in tool_id:
        return tool_id.rsplit("/", 1)[1]
    return None


def _versionless_tool_id(tool_id):
    if 'repos' in tool_id:
        return tool_id.rsplit("/", 1)[0]
    else:
        return tool_id


def _version_sorted_keys(versions_dict: Dict[str, Any]) -> List[str]:
    return version_sorted_iterable(versions_dict.keys())


def version_sorted_iterable(iterable) -> List[str]:
    return list(sorted(iterable, key=packaging.version.parse, reverse=True))
