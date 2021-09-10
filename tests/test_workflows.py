from gx_tool_db.workflows import parse_tool_ids
from ._data import DATA_DIRECTORY, EXAMPLE_WORKFLOW_1


def test_parse_ids():
    tool_ids = parse_tool_ids(EXAMPLE_WORKFLOW_1)
    assert "cat1" not in tool_ids
    assert "toolshed.g2.bx.psu.edu/repos/iuc/samtools_view/samtools_view/1.9+galaxy2" in tool_ids
    assert "toolshed.g2.bx.psu.edu/repos/bgruening/split_file_to_collection/split_file_to_collection/0.5.0" not in tool_ids

    more_tool_ids = parse_tool_ids(DATA_DIRECTORY)
    assert len(more_tool_ids) > len(tool_ids)
    assert "toolshed.g2.bx.psu.edu/repos/iuc/samtools_view/samtools_view/1.9+galaxy2" in more_tool_ids
    assert "toolshed.g2.bx.psu.edu/repos/bgruening/split_file_to_collection/split_file_to_collection/0.5.0" in more_tool_ids
