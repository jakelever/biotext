import bioc
import pytest
import requests


def fetch_fulltext(pmc_id: str) -> str:
    """
    https://www.ncbi.nlm.nih.gov/pmc/tools/get-full-text/
    """
    efetch_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
    resp = requests.get(efetch_url, params={'db': 'pmc', 'id': pmc_id})
    resp.raise_for_status()
    return resp.text


@pytest.fixture(scope='module')
def table_article():
    article = fetch_fulltext('PMC3203921')  # has a table to be processed in it
    return article


def test_convert_pmc_with_table():
    pass
