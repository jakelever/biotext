import os

import requests


def fetch_xml(pmc_id: str, db_name='pmc') -> str:
    """
    https://www.ncbi.nlm.nih.gov/pmc/tools/get-full-text/
    """
    efetch_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
    resp = requests.get(efetch_url, params={'db': db_name, 'id': pmc_id, 'rettype': 'xml'})
    resp.raise_for_status()
    return resp.text


def data_file_path(filepath):
    return os.path.join(os.path.dirname(__file__), 'data', filepath)
