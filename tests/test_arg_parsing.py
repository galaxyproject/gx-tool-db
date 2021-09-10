from gx_tool_db.main import arg_parser


def test_argparser():
    parser = arg_parser()
    args = parser.parse_args(["export-tabular", "--all-labels"])
    assert args.output == "gxtdb_output.tsv"
    assert args.labels == "*"

    args = parser.parse_args(["export-tabular", "--label", "moo", "--label", "cow"])
    assert args.labels == ["moo", "cow"]
    assert args.require_labels == []
    assert args.exclude_labels == []

    args = parser.parse_args(["export-tabular", "--label", "moo", "--label", "cow", "--require-label", "foobar", "--exclude-label", "moocow"])
    assert args.labels == ["moo", "cow"]
    assert args.require_labels == ["foobar"]
    assert args.exclude_labels == ["moocow"]
