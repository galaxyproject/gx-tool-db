import tempfile
from typing import Any, List

import gspread
from pkg_resources import resource_string

from .io import (
    csv_reader,
    csv_writer,
)

# credentials to confirm what app this is - configured by John.
CREDENTIALS_FILENAME = "credentials.json"
# token storing authenticated
TOKEN_FILENAME = "token.json"

LOCAL_TSV_DATA_FILENAME = 'local_data.tsv'

CSV_KWDS = dict(delimiter="\t", quotechar='"')

REQUIRED_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]


def get_client():
    with tempfile.NamedTemporaryFile() as f:
        credentials_str = resource_string(__name__, CREDENTIALS_FILENAME)
        f.write(credentials_str)
        f.flush()
        gc = gspread.oauth(
            credentials_filename=f.name,
            authorized_user_filename=TOKEN_FILENAME,
            scopes=REQUIRED_SCOPES,
        )
        return gc


def get_worksheet(spreadsheet_id: str):
    gc = get_client()

    spreadsheet = gc.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.worksheets()[0]
    return worksheet


def download_sheet_to_path(spreadsheet_id: str, output: str):
    with csv_writer(output) as writer:
        writer.writerows(download_sheet_to_list(spreadsheet_id))


def download_sheet_to_list(spreadsheet_id: str) -> List[List[Any]]:
    worksheet = get_worksheet(spreadsheet_id)
    return worksheet.get_all_values()


def upload_sheet_from_path(input: str, spreadsheet_id: str) -> None:
    with csv_reader(input) as reader:
        res = list(reader)
    upload_sheet_from_list(res, spreadsheet_id)


def upload_sheet_from_list(rows: List[List[Any]], spreadsheet_id) -> None:
    worksheet = get_worksheet(spreadsheet_id)
    worksheet.clear()
    worksheet.spreadsheet.values_append("Sheet1", {'valueInputOption': 'USER_ENTERED'}, {'values': rows})
