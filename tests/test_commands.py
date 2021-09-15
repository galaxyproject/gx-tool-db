import os
import tempfile
from pathlib import Path

import pytest
import yaml

from gx_tool_db.io import csv_dict_reader
from gx_tool_db.main import main
from gx_tool_db.models import load_from_path, ToolDatabase
from ._data import (
    COOL_LABELS_CSV,
    DEPRECATED_TOOLS,
    EXAMPLE_WORKFLOW_1,
    RESULTS_JSON,
)


DEPRECATED_TOOLS_URL = (
    "https://gist.githubusercontent.com/jmchilton/651dad1289cb897cfaa92a86a39a184e/raw/65da6b11353732b550f9b1e0f9dc218a6bcef916/gistfile1.txt"
)

DEFAULT_TEST_SERVER = "eu"
TEST_SERVER = os.environ.get("GX_TOOL_DB_TEST_SERVER", DEFAULT_TEST_SERVER)


@pytest.fixture(scope="module")
def usegalaxy_metadata_dir():
    original_working_dir = os.getcwd()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            main(["import-server", "--server", TEST_SERVER])
            yield Path(tmpdir)
    finally:
        os.chdir(original_working_dir)


def test_validation(usegalaxy_metadata_dir):
    tool_database: ToolDatabase = load_from_path()
    verify_usegalaxy_tool_panel_skeleton(tool_database)


def test_export_coverage(usegalaxy_metadata_dir):
    main(["export-tabular", "--output", "foo.tsv", "--all-coverage"])
    output = Path("foo.tsv").read_text("utf-8")
    assert "__DATA_FETCH__" in output
    assert "," not in output
    assert output.startswith("Tool ID\tLatest Version")

    main(["export-tabular", "--output", "foo.csv", "--all-coverage"])
    output = Path("foo.csv").read_text("utf-8")
    assert output.startswith("Tool ID,Latest Version")


def test_export_coverage_versions(usegalaxy_metadata_dir):
    main(["export-coverage-versions", "--output", "foo.tsv"])
    output = Path("foo.tsv").read_text("utf-8")
    assert "__DATA_FETCH__" in output
    assert "," not in output
    assert output.startswith("Tool ID\tTool Version\tLatest Version\tIs Latest Version")


def test_export_install_yaml(usegalaxy_metadata_dir):
    main(["export-install-yaml"])
    repos = load_tools_yaml_repos()
    assert len(repos) > 40


def test_labelling(usegalaxy_metadata_dir):
    main(["import-labels", COOL_LABELS_CSV])
    main(["import-label", DEPRECATED_TOOLS, "deprecated"])
    main(["import-label", DEPRECATED_TOOLS_URL, "deprecated2"])
    load_from_path()  # validate contents with labels added

    main(["export-label", "db_deprecated_ids.txt", "deprecated"])
    main(["export-label", "db_deprecated2_ids.txt", "deprecated2"])
    main(["export-label", "db_awesome_ids.txt", "awesome"])

    db_deprecated_ids = Path("db_deprecated_ids.txt").read_text("utf-8")
    assert "toolshed.g2.bx.psu.edu/repos/devteam/cummerbund_to_tabular/cummerbund_to_cuffdiff" in db_deprecated_ids
    db_awesome_ids = Path("db_awesome_ids.txt").read_text("utf-8")
    assert "toolshed.g2.bx.psu.edu/repos/iuc/sqlite_to_tabular/sqlite_to_tabular" in db_awesome_ids

    db_deprecated_ids = Path("db_deprecated2_ids.txt").read_text("utf-8")
    assert "toolshed.g2.bx.psu.edu/repos/devteam/cummerbund_to_tabular/cummerbund_to_cuffdiff" in db_deprecated_ids


def test_exclude_label(usegalaxy_metadata_dir):
    main(["import-label", DEPRECATED_TOOLS, "deprecated"])
    repos = load_tools_yaml_repos()
    found_ctt = False
    for repo in repos:
        found_ctt = found_ctt or repo["name"] == "cummerbund_to_tabular"

    assert found_ctt

    main(["export-install-yaml", "--exclude-label", "deprecated"])
    repos = load_tools_yaml_repos()
    found_ctt = False
    for repo in repos:
        found_ctt = found_ctt or repo["name"] == "cummerbund_to_tabular"
    assert not found_ctt


def test_require_label(usegalaxy_metadata_dir):
    main(["import-labels", COOL_LABELS_CSV])
    main(["export-install-yaml", "--require-label", "awesome"])
    repos = load_tools_yaml_repos()
    assert len(repos) == 3


def test_load_test_data(usegalaxy_metadata_dir):
    main(["import-tests", RESULTS_JSON, "anvil"])
    load_from_path()
    command_1 = ["export-tabular", "--output", "foo.csv", "--test", "anvil"]
    command_2 = ["export-tabular", "--output", "foo.csv", "--all-tests"]
    for command in [command_1, command_2]:
        main(command)
        deeptools_bam_coverage_found = False
        with csv_dict_reader("foo.csv") as reader:
            for row in reader:
                tool_id = row["Tool ID"]
                assert "anvil Test Count" in row.keys(), list(row.keys())
                if tool_id == "toolshed.g2.bx.psu.edu/repos/bgruening/deeptools_bam_coverage/deeptools_bam_coverage":
                    deeptools_bam_coverage_found = True
                    assert row["anvil Test Count"] == "7"
                    assert row["anvil Tests Failed"] == "7"

        assert deeptools_bam_coverage_found


def test_export_view_require(usegalaxy_metadata_dir):
    main(["import-labels", COOL_LABELS_CSV])
    main(["export-panel-view", "awesome", TEST_SERVER, "--require-label", "awesome"])
    view_yml = Path("awesome.yml")
    assert view_yml.exists()
    with open(view_yml, "r") as f:
        view_dict = yaml.safe_load(f)
    assert view_dict["id"] == "awesome"
    assert view_dict["type"] == "generic"
    assert "excludes" not in view_dict
    assert "items" in view_dict


def test_export_view_exclude(usegalaxy_metadata_dir):
    main(["import-labels", COOL_LABELS_CSV])
    main(["export-panel-view", "no_meh", TEST_SERVER, "--output", "not_a_single_meh_tool.yml", "--exclude-label", "meh"])
    view_yml = Path("not_a_single_meh_tool.yml")
    assert view_yml.exists()
    with open(view_yml, "r") as f:
        view_dict = yaml.safe_load(f)
    assert view_dict["id"] == "no_meh"
    assert view_dict["type"] == "generic"
    assert "excludes" in view_dict
    assert "items" in view_dict


def test_label_workflow_tools(usegalaxy_metadata_dir):
    main(["label-workflow-tools", EXAMPLE_WORKFLOW_1, "--label", "iwc_required"])
    main(["export-label", "iwc_required_tools.txt", "iwc_required"])
    all_tool_ids = Path("iwc_required_tools.txt").read_text("utf-8")
    assert "toolshed.g2.bx.psu.edu/repos/iuc/samtools_view/samtools_view" in all_tool_ids


def verify_usegalaxy_tool_panel_skeleton(tool_database: ToolDatabase):
    # sort of brittle, but check that the recorded skeleton looks like usegalaxy.orgs
    assert tool_database.integrated_panels
    main_panel = tool_database.integrated_panels[TEST_SERVER].__root__
    assert len(main_panel) > 0
    get_data = main_panel[0]
    assert get_data.model_class == "ToolSection"
    assert get_data.name == "Get Data"

    first_label = [e for e in main_panel if e.model_class == "ToolSectionLabel"][0]
    assert first_label.text.upper() == "GENERAL TEXT TOOLS"


def load_tools_yaml_repos(path="tools.yaml"):
    tools_yaml = Path("tools.yaml")
    assert tools_yaml.exists()
    with open(tools_yaml, "r") as f:
        install_dict = yaml.safe_load(f)
        assert "tools" in install_dict
        repos = install_dict["tools"]
        return repos
