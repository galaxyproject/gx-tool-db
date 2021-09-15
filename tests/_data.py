import os

SCRIPT_DIRECTORY = os.path.abspath(os.path.dirname(__file__))
DATA_DIRECTORY = os.path.join(SCRIPT_DIRECTORY, "data")
DEPRECATED_TOOLS = os.path.join(DATA_DIRECTORY, "deprecated_tools.txt")
COOL_LABELS_CSV = os.path.join(DATA_DIRECTORY, "cool_labels.csv")
# Test results from:
#  https://raw.githubusercontent.com/almahmoud/anvil-misc/master/reports/anvil-production/tool-tests/gxy-auto-06-26-04-08-34-1/results.json
RESULTS_JSON = os.path.join(DATA_DIRECTORY, "results.json")
EXAMPLE_WORKFLOW_1 = os.path.join(DATA_DIRECTORY, "pe-wgs-variation.ga")
EXAMPLE_WORKFLOW_NESTED = os.path.join(DATA_DIRECTORY, "subworkflow.ga")
MOCK_TRAINING_DIRECTORY = os.path.join(DATA_DIRECTORY, "mock_training")
