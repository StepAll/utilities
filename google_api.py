import json
import pandas as pd

from dataclasses import dataclass

import httplib2
import apiclient.discovery
from oauth2client.service_account import ServiceAccountCredentials


@dataclass
class GSPage:
    """GoogleSheet page"""
    service_account_json:str
    gs_id:str
    page_name:str
    page_id:str


# google api
def get_google_service(service_account_json:str, api:str='sheets'):
    """return connection to google api
    api='sheets'
    api='drive'
    """
    service_account_file_json = json.loads(service_account_json, strict=False)
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(service_account_file_json, ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
    httpAuth = credentials.authorize(httplib2.Http())
    if api == 'sheets':
        return apiclient.discovery.build('sheets', 'v4', http = httpAuth)
    elif api == 'drive':
        return apiclient.discovery.build('drive', 'v3', credentials=credentials)
    return None

def get_gs_table(service, gs_id:str, gs_page_name:str) -> pd.DataFrame:
    """ Get Google Sheet's page"""
    result = service.spreadsheets().values().batchGet(spreadsheetId=gs_id, ranges=gs_page_name).execute()
    columns = result['valueRanges'][0]['values'][0]
    data = result['valueRanges'][0]['values'][1:]
    df = pd.DataFrame(data=data, columns=columns)
    return df