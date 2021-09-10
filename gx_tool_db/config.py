"""Configuration related constants and objects.
"""
from typing import List, Optional, Type, Union

DEFAULT_DATABASE_PATH = "tools_metadata.yml"

USEGALAXY_ORG_URL = "https://usegalaxy.org"
TEST_URL = "https://test.galaxyproject.org"
USEGALAXY_EU_URL = "https://usegalaxy.eu"
USEGALAXY_AU_URL = "htttps://usegalaxy.org.au"

SERVER_LABELS = {
    USEGALAXY_ORG_URL: 'main',
    TEST_URL: 'test',
    USEGALAXY_EU_URL: 'eu',
    USEGALAXY_AU_URL: 'au',
}

PUBLIC_SERVERS = [
    USEGALAXY_ORG_URL,
    TEST_URL,
    USEGALAXY_EU_URL,
    USEGALAXY_AU_URL,
]

DEFAULT_PANEL_VIEW_TYPE = "generic"


class FilterArguments:
    require_labels: Optional[List[str]] = None
    exclude_labels: Optional[List[str]] = None

    def __init__(self, require_labels=None, exclude_labels=None):
        self.require_labels = require_labels
        self.exclude_labels = exclude_labels


class Server:
    url: str
    key: Optional[str]

    def __init__(self, url: str, key: Optional[str] = None):
        self.url = url
        self.key = key

    @property
    def label(self):
        url = self.url
        return SERVER_LABELS.get(url, url)


class ViewDefintion(FilterArguments):
    id: str
    output: Optional[str] = None
    view_type: str = DEFAULT_PANEL_VIEW_TYPE
    description: Optional[str] = None

    def __init__(self, id):
        self.id = id

    @property
    def effective_output(self):
        return self.output if self.output else f"{self.id}.yml"


class AllData:
    pass


ALL_SERVER_LABELS = AllData()
ALL_TEST_LABELS = AllData()
ALL_LABELS = AllData()


class ExportSpreadsheetConfig(FilterArguments):
    output: str
    coverage: Union[List[str], Type[AllData]]
    tests: Union[List[str], Type[AllData]]
    labels: Union[List[str], Type[AllData]]

    def __init__(self, args):
        self.output = args.output
        if args.coverage == "*":
            self.coverage = ALL_SERVER_LABELS
        else:
            self.coverage = args.coverage
        if args.tests == "*":
            self.tests = ALL_TEST_LABELS
        else:
            self.tests = args.tests
        if args.labels == "*":
            self.labels = ALL_LABELS
        else:
            self.labels = args.labels
        self.require_labels = args.require_labels
        self.exclude_labels = args.exclude_labels
