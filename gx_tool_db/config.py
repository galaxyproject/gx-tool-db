"""Configuration related constants and objects.
"""
from enum import Enum
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
    "https://clipseq.usegalaxy.eu/": "cliqseq_eu",
    "https://humancellatlas.usegalaxy.eu/": "humancellatlas_eu",
    "https://metabolomics.usegalaxy.eu/": "metabolomics_eu",
    "https://ml.usegalaxy.eu/": "ml_eu",
    "https://proteomics.usegalaxy.eu/": "proteomics_eu",
    "https://annotation.usegalaxy.eu/": "annotation_eu",
    "https://cheminformatics.usegalaxy.eu/": "cheminformatics_eu",
    "https://covid19.usegalaxy.eu/": "covid19_eu",
    "https://graphclust.usegalaxy.eu/": "graphclust_eu",
    "https://imaging.usegalaxy.eu/": "imaging_eu",
    "https://metagenomics.usegalaxy.eu/": "metagenomics_eu",
    "https://nanopore.usegalaxy.eu/": "nanopore_eu",
    "https://rna.usegalaxy.eu/": "rna_eu",
    "https://assembly.usegalaxy.eu/": "assembly_eu",
    "https://climate.usegalaxy.eu/": "climate_eu",
    "https://ecology.usegalaxy.eu/": "ecology_eu",
    "https://hicexplorer.usegalaxy.eu/": "hicexplorer_eu",
    "https://microbiome.usegalaxy.eu/": "microbiome_eu",
    "https://plants.usegalaxy.eu/": "plants_eu",
    "https://singlecell.usegalaxy.eu/": "singlecell_eu",
}

URLS_BY_LABEL = {v: k for (k, v) in SERVER_LABELS.items()}

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


class TestDataMergeStrategy(str, Enum):
    latest_added = 'latest_added'
    latest_executed = 'latest_executed'
    best = 'best'

    latest_added_indexwise = 'latest_added_indexwise'
    latest_executed_indexwise = 'latest_executed_indexwise'
    best_indexwise = 'best_indexwise'


class ExportSpreadsheetConfig(FilterArguments):
    output: str
    coverage: Union[List[str], Type[AllData]]
    tests: Union[List[str], Type[AllData]]
    labels: Union[List[str], Type[AllData]]

    include_training_topics: bool = False
    include_training_tutorials: bool = False
    include_name: bool = False
    include_description: bool = False
    include_model_class: bool = False
    include_tool_shed: bool = False
    include_repository_owner: bool = False
    include_repository_name: bool = False

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
        self.include_training_topics = args.training_topics
        self.include_training_tutorials = args.training_tutorials

        self.include_name = args.name
        self.include_description = args.description
        self.include_model_class = args.model_class
        self.include_tool_shed = args.tool_shed
        self.include_repository_owner = args.repository_owner
        self.include_repository_name = args.repository_name
