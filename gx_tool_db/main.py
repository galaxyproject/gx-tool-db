"""
TODO:

- click or something else to cleanup argparsing...
- remove latest version from the def, it can just be calculated in realtime
- test case for subworkflows

- load in usage data (tool runs, error percent, etc...) from target servers - probably using gxadmin(?)
"""
import argparse
import io
import json
import sys
from typing import Any, cast, List, Optional

import requests
import urllib3
import yaml

from .config import (
    ALL_LABELS,
    ALL_SERVER_LABELS,
    ALL_TEST_LABELS,
    DEFAULT_DATABASE_PATH,
    DEFAULT_PANEL_VIEW_TYPE,
    ExportSpreadsheetConfig,
    FilterArguments,
    PUBLIC_SERVERS,
    Server,
    USEGALAXY_ORG_URL,
    ViewDefintion,
)
from .db import (
    _versionless_tool_id,
    FilterCriteria,
    ToolLatestTestResults,
    ToolsMetadata,
    ToolVersionEntry,
)
from .io import (
    csv_reader,
    csv_writer,
    warn,
)
from .sheets import (
    download_sheet_to_list,
    download_sheet_to_path,
    upload_sheet_from_list,
    upload_sheet_from_path,
)
from .workflows import parse_tool_ids


COLUMN_HEADER_TOOL_ID = "Tool ID"
COLUMN_HEADER_TOOL_VERSION = "Tool Version"
COLUMN_HEADER_LATEST_VERSION = "Latest Version"

DEFAULT_EXPORT_TYPE = "tsv"  # or csv
REPORT_PREFIX = "gxtdb_"
OUTPUT_DEFAULT_SPREADSHEET = f"{REPORT_PREFIX}output.{DEFAULT_EXPORT_TYPE}"
OUTPUT_DEFAULT_COVERAGE_VERSIONS = f"{REPORT_PREFIX}coverage_versions.{DEFAULT_EXPORT_TYPE}"

SHEET_TARGET_PREFIX = "sheet:"


class Config:
    metadata_file: str

    def __init__(self, metadata_file: str):
        self.metadata_file = metadata_file


class TestResults:

    def __init__(self, path):
        results = {}
        with _open_uri(path) as f:
            results = json.load(f)
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


def bootstrap_tools_metadata(config: Config, server: Server):
    tools_metadata = ToolsMetadata(config.metadata_file)

    out_panel = tools_request(server=server, in_panel=False)
    in_panel = tools_request(server=server, in_panel=True)

    for tool in out_panel:
        tool_entry = tools_metadata.get_entry_for_api_value(tool, server)
        tool_version = tool["version"]
        tool_version_entry = tool_entry.get_version_entry(tool_version)
        repo = tool.get("tool_shed_repository", None)
        tool_entry.record_ts_repo(repo)
        labels = tool['labels']
        tool_version_entry.record_labels(labels)

    for entry in in_panel:
        if entry["model_class"] != "ToolSection":
            continue
        section_id = entry["id"]
        section_name = entry["name"]
        for section_elem in entry.get("elems", []):
            if section_elem["model_class"] != "Tool":
                continue
            tool_entry = tools_metadata.get_entry_for_api_value(section_elem, server)
            tool_entry.record_section(section_id, section_name)

    integrated_panel_skeleton = []
    for entry in in_panel:
        model_class = entry.get("model_class")
        if model_class not in ["ToolSectionLabel", "ToolSection"]:
            continue
        element = {
            "model_class": model_class,
            "id": entry["id"],
        }
        if model_class == "ToolSectionLabel":
            element["text"] = entry["text"]
        elif model_class == "ToolSection":
            element["name"] = entry["name"]
        integrated_panel_skeleton.append(element)

    tools_metadata.record_panel_skeleton(integrated_panel_skeleton, server)
    tools_metadata.write()


def tools_request(server: Server, in_panel=False):
    url = server.url
    api_key = server.key
    api_url = url + f"/api/tools?in_panel={str(in_panel).lower()}"
    if api_key:
        api_url += "&key={api_key}"
    response = requests.get(api_url)
    response.raise_for_status()
    return response.json()


def _export_spreadsheet(output: str, all_rows: List[List[Any]]):
    if output.startswith(SHEET_TARGET_PREFIX):
        output_sheet_id = output[len(SHEET_TARGET_PREFIX):]
        upload_sheet_from_list(all_rows, output_sheet_id)
    else:
        path = output
        with csv_writer(path) as writer:
            writer.writerows(all_rows)


def _import_spreadsheet(input: str) -> List[List[Any]]:
    if input.startswith(SHEET_TARGET_PREFIX):
        input_sheet_id = input[len(SHEET_TARGET_PREFIX):]
        return download_sheet_to_list(input_sheet_id)
    else:
        return _read_csv(input)


def _read_csv(path):
    with csv_reader(path) as reader:
        return list(reader)


def import_tabular(config, path, labels):
    all_data = _read_csv(path)
    header = all_data[0]
    rest = all_data[1:]
    header_index = {}
    for i, header_value in enumerate(header):
        header_index[header_value] = i
    tools_metadata = ToolsMetadata(config.metadata_file)
    for data in rest:
        tool_id_index = header_index[COLUMN_HEADER_TOOL_ID]
        tool_id = data[tool_id_index]
        tool_entry = tools_metadata.get_entry_for(tool_id)
        for label in labels:
            label_index = header_index[label]
            label_value = data[label_index]
            present = None
            if str(label_value).lower() in ["none", "null", "", "0", "false"]:
                present = False
            elif str(label_value).lower() in ["1", "true"]:
                present = True
            if present is None:
                raise Exception(f"Do not know how to process label value {label_value} from spreadsheet")
            tool_entry.record_external_label(label, present=present)
    tools_metadata.write()


def label_workflow_tools(config: Config, input: str, labels: List[str]):
    tool_ids = parse_tool_ids(input)
    tools_metadata = ToolsMetadata(config.metadata_file)
    for raw_tool_id in tool_ids:
        tool_id = _versionless_tool_id(raw_tool_id)
        tool_entry = tools_metadata.get_entry_for(tool_id)
        if tool_entry is None:
            warn(f"Failed to find entry for {tool_id} while attempting to label workflow tools")
        for label in labels:
            tool_entry.record_external_label(label)
    tools_metadata.write()


def import_test_results(config, path, test_target):
    test_results = TestResults(path)
    tools_metadata = ToolsMetadata(config.metadata_file)
    for tool_id, results in test_results.results_by_id.items():
        for result in results:
            tool_version = result["tool_version"]
            tool_entry = tools_metadata.get_entry_for(tool_id)
            tool_version_entry = tool_entry.get_version_entry(tool_version)
            tool_version_entry.record_test_result(test_target, result)

    tools_metadata.write()


def export_coverage(config, export_config: ExportSpreadsheetConfig):
    rows = []
    tools_metadata = ToolsMetadata(config.metadata_file)

    # Assemble header...

    # Assemble coverage headers...
    if export_config.coverage is ALL_SERVER_LABELS:
        coverage_servers = tools_metadata.known_servers()
    else:
        coverage_servers = cast(List[str], export_config.coverage)

    header = [COLUMN_HEADER_TOOL_ID, COLUMN_HEADER_LATEST_VERSION]
    for server in coverage_servers:
        header.append(f"{server} Latest Version")
        header.append(f"{server} Is Latest")

    # Assemble test headers...
    if export_config.tests is ALL_TEST_LABELS:
        test_keys = tools_metadata.test_keys()
    else:
        test_keys = cast(List[str], export_config.tests)

    for test_key in test_keys:
        header.append(f"{test_key} Latest Version Tested")
        header.append(f"{test_key} Is Latest Version Tested")
        header.append(f"{test_key} Test Count")
        header.append(f"{test_key} Tests Passed")
        header.append(f"{test_key} Tests Failed")
        header.append(f"{test_key} Any Tests Passed")

    if export_config.labels is ALL_LABELS:
        raise NotImplementedError("TODO...")
    else:
        labels = cast(List[str], export_config.labels)

    # Handle labels...
    header.extend(labels)

    rows.append(header)

    filter_criteria = FilterCriteria()
    filter_criteria.exclude_labels = export_config.exclude_labels
    filter_criteria.require_labels = export_config.require_labels

    for tool_entry in tools_metadata.entries(filter_criteria=filter_criteria):
        tool_id = tool_entry.tool_id
        tool_metadata = tool_entry._source_data

        # Add coverage columns (if any)
        latest_version = tool_metadata["latest_version"]
        row = [tool_id, latest_version]
        coverage_servers_dict = {key: "" for key in coverage_servers}
        for server, server_dict in tool_metadata.get("servers", {}).items():
            coverage_servers_dict[server] = server_dict["latest_version"]
        for known_server in coverage_servers:
            row.append(coverage_servers_dict[known_server])
            row.append(spreadsheet_bool(coverage_servers_dict[known_server] == latest_version))

        # Add test columns (if any)
        latest_test_results_dict = tool_entry.get_latest_test_results_dict()
        for test_key in test_keys:
            tool_latest_test_results: Optional[ToolLatestTestResults] = latest_test_results_dict.get(test_key)
            if not tool_latest_test_results or not tool_latest_test_results.test_results:
                row.append("")
                row.append("0")
                row.append("0")
                row.append("0")
                row.append("")
                row.append("0")
            else:
                # tool_latest_test_results has version and latest test results...
                tool_version_entry: ToolVersionEntry = tool_latest_test_results.tool_version_entry
                test_results: dict = tool_latest_test_results.test_results
                row.append(tool_version_entry.tool_version)
                row.append(spreadsheet_bool(tool_version_entry.tool_version == latest_version))
                row.append(str(len(test_results)))
                passed = 0
                failed = 0
                for _, test_result in test_results.items():
                    status = test_result.get("status")
                    if status == "success":
                        passed += 1
                    elif status in ["failed", "error"]:
                        failed += 1
                    else:
                        warn(f"Unknown test result status encountered {status}")
                row.append(str(passed))
                row.append(str(failed))
                row.append(spreadsheet_bool(passed > 0))

        for label in labels:
            value = spreadsheet_bool(tool_entry.has_external_label(label))
            row.append(value)
        rows.append(row)
    _export_spreadsheet(export_config.output, rows)


def export_coverage_versions(config, output_name=OUTPUT_DEFAULT_COVERAGE_VERSIONS):
    rows = []
    tools_metadata = ToolsMetadata(config.metadata_file)
    known_servers = tools_metadata.known_servers()
    header = [COLUMN_HEADER_TOOL_ID, COLUMN_HEADER_TOOL_VERSION, COLUMN_HEADER_LATEST_VERSION, "Is Latest Version"]
    for server in known_servers:
        header.append(f"{server} Has Version")
    rows.append(header)
    for tool_entry in tools_metadata.entries():
        tool_id = tool_entry.tool_id
        tool_metadata = tool_entry._source_data
        latest_version = tool_metadata["latest_version"]
        for tool_version, tool_version_metadata in tool_metadata.get("versions", {}).items():
            row = [tool_id, tool_version, latest_version]
            known_servers_dict = {key: spreadsheet_bool(False) for key in known_servers}
            for server in tool_version_metadata.get("servers", {}).keys():
                known_servers_dict[server] = spreadsheet_bool(True)
            for known_server in known_servers:
                row.append(known_servers_dict[known_server])
            rows.append(row)
    _export_spreadsheet(output_name, rows)


def spreadsheet_bool(val):
    return "1" if val else "0"


def clear_test_results(config, test_target):
    tools_metadata = ToolsMetadata(config.metadata_file)
    tools_metadata.clear_test_results(test_target)
    tools_metadata.write()


def clear_label(config, label_key):
    tools_metadata = ToolsMetadata(config.metadata_file)
    tools_metadata.clear_label(label_key)
    tools_metadata.write()


def google_export(input, sheet_id):
    upload_sheet_from_path(input, sheet_id)


def google_import(sheet_id, output):
    download_sheet_to_path(sheet_id, output)


def export_install_yaml(config: Config, output: str, servers: List[str], filter_args: FilterArguments):
    tools_metadata = ToolsMetadata(config.metadata_file)
    install_dict = tools_metadata.install_dict(servers, filter_args)
    with open(output, "w") as f:
        yaml.safe_dump(install_dict, f)


def export_panel_view(config: Config, server: str, view_def: ViewDefintion):
    tools_metadata = ToolsMetadata(config.metadata_file)
    view_dict = tools_metadata.panel_view_dict(server, view_def)
    output_path = view_def.effective_output
    print(output_path)
    with open(output_path, "w") as f:
        yaml.safe_dump(view_dict, f)


def import_labels(config, input):
    inputs = _import_spreadsheet(input)
    tool_id_pairs = []
    for input in inputs:
        if len(input) < 2:
            raise Exception(f"Invalid label tabular data - parsed as line - {input}")
        tool_id_pairs.append((input[0], input[1]))
    _import_labels(config, tool_id_pairs)


def import_label(config, input, label):
    with _open_uri(input) as f:
        contents = f.read()
    tool_ids = [line.strip() for line in contents.split("\n")]
    tool_id_pairs = [(t_i, label) for t_i in tool_ids]
    _import_labels(config, tool_id_pairs)


def _import_labels(config, tool_id_pairs):
    tools_metadata = ToolsMetadata(config.metadata_file)
    for tool_entry in tools_metadata.entries():
        entry_tool_id = tool_entry._tool_id
        for (tool_id, label) in tool_id_pairs:
            if entry_tool_id == tool_id:
                tool_entry.record_external_label(label)
    tools_metadata.write()


def export_label(config, output, label):
    tools_metadata = ToolsMetadata(config.metadata_file)
    tool_ids = []
    for tool_entry in tools_metadata.entries():
        if tool_entry.has_external_label(label):
            tool_ids.append(tool_entry._tool_id)
    with open(output, "w") as f:
        f.write("\n".join(tool_ids))


def arg_parser():
    parser = argparse.ArgumentParser(description="Manage runtime metadata about tools across Galaxy servers")
    parser.add_argument('--tools_metadata', type=str, help='File containing merged tools metadata (YAML)', default=DEFAULT_DATABASE_PATH)

    subparsers = parser.add_subparsers(dest="command")
    parser_dump = subparsers.add_parser('import-server', help='import runtime metadata from a target Galaxy server')
    parser_dump.add_argument('--url', type=str, help='Galaxy server', default=USEGALAXY_ORG_URL)
    parser_dump.add_argument('--api_key', type=str, help='API Key (optional)', default=None)

    subparsers.add_parser('import-server-all', help='dump all metadata form usegalaxy.org and usegalaxy.eu')

    HELP_ARG_OUTPUT = 'Report file to output (csv or tsv)'
    HELP_EXPORT_COVERAGE = 'export spreadsheet summary of data'
    parser_export_tabular = subparsers.add_parser('export-tabular', help=HELP_EXPORT_COVERAGE)
    add_common_filters(parser_export_tabular)
    parser_export_tabular.add_argument('--output', type=str, help=HELP_ARG_OUTPUT, default=OUTPUT_DEFAULT_SPREADSHEET)

    coverage_group = parser_export_tabular.add_mutually_exclusive_group()
    coverage_group.add_argument("--coverage", dest="coverage", action="append", help="", default=[])
    coverage_group.add_argument("--all-coverage", dest="coverage", action="store_const", const="*", help="")

    tests_group = parser_export_tabular.add_mutually_exclusive_group()
    tests_group.add_argument("--test", dest="tests", action="append", help="", default=[])
    tests_group.add_argument("--all-tests", dest="tests", action="store_const", const="*", help="")

    labels_group = parser_export_tabular.add_mutually_exclusive_group()
    labels_group.add_argument("--label", dest="labels", action="append", help="", default=[])
    labels_group.add_argument("--all-labels", dest="labels", action="store_const", const="*", help="")

    HELP_EXPORT_COVERAGE_VERSIONS = 'export coverage of tool versions across servers'
    parser_export_coverage_versions = subparsers.add_parser('export-coverage-versions', help=HELP_EXPORT_COVERAGE_VERSIONS)
    parser_export_coverage_versions.add_argument('--output', type=str, help=HELP_ARG_OUTPUT, default=OUTPUT_DEFAULT_COVERAGE_VERSIONS)

    parser_import_tabular = subparsers.add_parser("import-tabular", help="import external label data from a spreadsheet")
    parser_import_tabular.add_argument('input', help='Input to read from')
    parser_import_tabular.add_argument(
        '--label', dest="labels", action='append', default=[], required=True, help='External label derived from column header'
    )

    parser_import_labels = subparsers.add_parser('import-labels', help='import external labels from a two column file')
    parser_import_labels.add_argument('input', help='Input to read from')

    parser_import_label = subparsers.add_parser('import-label', help='read file of tool ids and assign label to each')
    parser_import_label.add_argument('input', help='Input to read from')
    parser_import_label.add_argument('label', help='label to attach to supplied tools')

    parser_export_label = subparsers.add_parser('export-label', help='write file containing tool IDs with tools matching specifying matching label')
    parser_export_label.add_argument('output', help='Output text file')
    parser_export_label.add_argument('label', help='label to check tools for')

    parser_label_workflow = subparsers.add_parser('label-workflow-tools', help='Label all the tool ids from a workflow')
    parser_label_workflow.add_argument('input', help='Input path or directory to read workflow(s) from')
    parser_label_workflow.add_argument('--label', action='append', default=[], required=True, help='Label to add to tool IDs')

    # TODO: we've got the abstractions...
    # parser_label_workflow = subparsers.add_parser('export-workflow-tools', help='write file containing tool IDs from a workflow')
    # parser_label_workflow.add_argument('input', help='Input path or directory to read workflow(s) from')

    parser_import_test_results = subparsers.add_parser('import-tests', help='import test results')
    parser_import_test_results.add_argument('input', help='Input to read from')
    parser_import_test_results.add_argument('test_target', help='Target of tool tests')

    parser_clear_test_results = subparsers.add_parser('clear-tests', help='clear test results for target server')
    parser_clear_test_results.add_argument('test_target', help='Target of tool tests')

    parser_clear_label = subparsers.add_parser('clear-label', help='clear external label on tools')
    parser_clear_label.add_argument('label', help='Label key for label to clear')

    parser_export_install = subparsers.add_parser('export-install-yaml', help='export tools.yaml file for installation')
    parser_export_install.add_argument('--output', type=str, help="Path to tools YAML file to create", default="tools.yaml")
    parser_export_install.add_argument('--server', action='append', default=[], required=False, help='Filter by specified server')
    add_common_filters(parser_export_install)

    parser_export_view = subparsers.add_parser('export-panel-view', help='export tool panel view')
    parser_export_view.add_argument('id', type=str, help="ID of tool panel to create")
    parser_export_view.add_argument('server', type=str, help='Server to use for tool panel backbone and section definitions')
    parser_export_view.add_argument('--output', type=str, help="Output YAML (defaults to <id>.yml", default=None)
    HELP_ARG_VIEW_TYPE = "Panel view type (generic, activity, publication, training, ...)"
    parser_export_view.add_argument('--view_type', type=str, help=HELP_ARG_VIEW_TYPE, default=DEFAULT_PANEL_VIEW_TYPE)
    parser_export_view.add_argument('--description', type=str, help="End user description of panel view.")
    add_common_filters(parser_export_view)

    # debugging commands...
    parser_g_export = subparsers.add_parser('_google-export', help='export a local spreadsheet to Google Sheets')
    parser_g_export.add_argument('input', help='Input to read spreadsheet from')
    parser_g_export.add_argument('sheet_id', help='ID of sheet to export to Google')

    parser_g_import = subparsers.add_parser('_google-import', help='import a Google Sheets spreadsheet to the local filesystem')
    parser_g_import.add_argument('sheet_id', help='ID of sheet to import from Google')
    parser_g_import.add_argument('output', help='Output location of spreadsheet to write')
    return parser


def add_common_filters(parser):
    parser.add_argument(
        '--require-label', dest="require_labels", action='append', default=[], required=False,
        help='Filter to only tools with specified required label'
    )
    parser.add_argument(
        '--exclude-label', dest="exclude_labels", action='append', default=[], required=False,
        help='Filter to exclude tools with specified label'
    )


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    parser = arg_parser()
    args = parser.parse_args(argv)
    config = Config(args.tools_metadata)
    command = args.command
    if command == "import-server":
        server = Server(args.url, args.api_key)
        bootstrap_tools_metadata(config, server)
    elif command == "import-server-all":
        servers = PUBLIC_SERVERS
        for server in servers:
            bootstrap_tools_metadata(config, Server(server, None))
    elif command == "import-tabular":
        labels = args.labels
        assert labels
        import_tabular(config, args.input, labels)
    elif command == "import-tests":
        import_test_results(config, args.input, args.test_target)
    elif command == "export-tabular":
        export_config = ExportSpreadsheetConfig(args)
        export_coverage(config, export_config)
    elif command == "export-coverage-versions":
        export_coverage_versions(config, args.output)
    elif command == "clear-tests":
        clear_test_results(config, args.test_target)
    elif command == "clear-label":
        clear_label(config, args.label)
    elif command == "export-install-yaml":
        filter_args = FilterArguments(args.require_labels, args.exclude_labels)
        export_install_yaml(config, args.output, args.server, filter_args)
    elif command == "import-labels":
        import_labels(config, args.input)
    elif command == "import-label":
        import_label(config, args.input, args.label)
    elif command == "export-label":
        export_label(config, args.output, args.label)
    elif command == "export-panel-view":
        view_def = ViewDefintion(args.id)
        view_def.output = args.output
        view_def.view_type = args.view_type
        view_def.description = args.description
        view_def.require_labels = args.require_labels
        view_def.exclude_labels = args.exclude_labels
        export_panel_view(config, args.server, view_def)
    elif command == "label-workflow-tools":
        labels = args.label
        assert labels
        label_workflow_tools(config, args.input, labels)
    elif command == "_google-export":
        google_export(args.input, args.sheet_id)
    elif command == "_google-import":
        google_import(args.sheet_id, args.output)
    else:
        raise Exception(f"Unknown command [{command}]")


def _open_uri(input_path_or_uri: str):
    if "://" not in input_path_or_uri:
        return open(input_path_or_uri, "r")
    else:
        http = urllib3.PoolManager()
        r = http.request('GET', input_path_or_uri, preload_content=False)
        r.auto_close = False
        return io.TextIOWrapper(r)


if __name__ == "__main__":
    main()
