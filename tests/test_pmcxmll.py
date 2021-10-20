from io import StringIO

import pytest
import requests
from bioconverters.pmcxml import pmcxml2bioc
from bioconverters.utils import TextChunk, tag_handler


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


def test_convert_pmc_with_table(table_article):
    file = StringIO(table_article)
    expected_content = "ERBB2 mutation  Exon  Functional region  Cancer type  Lapatinib  AEE788  Reference      WT  NA  NA  Breast cancer  30  257  NA    L755S  19  ATP binding region  Breast and gastric cancer  >2000  897  4    L755P  19  ATP binding region  NSCLC  1545  1216  2,3    V773A  20  ATP binding region  SCCHN  146  200  6    V777L  20  ATP binding region  Gastric, colon and lung  27  215  3,4    T798M  20  Gate keeper residue  NA  1433  >2000  NA    N857S  21  Activation loop  Ovarian cancer  75  246  2    T862A  21  Activation loop  Primary gastric cancer  125  191  7    H878Y  21  Activation loop  Hepatocellular carcinoma  14  168  5"
    all_passages = []
    for doc in pmcxml2bioc(file, trim_sentences=False, paths_infon=True):
        all_passages.extend(doc.passages)
    assert expected_content in [
        p.text for p in all_passages if p.infons.get('xml_path', '').endswith('table')
    ]


def test_custom_tag_handler(table_article):
    expected_content = 'SOME DUMMY CAPTION TEXT'
    all_passages = []
    file = StringIO(table_article)

    def dummy_handler(elem, custom_handlers):
        return [TextChunk(expected_content, None, '')]

    for doc in pmcxml2bioc(file, tag_handlers={'caption': dummy_handler}):
        all_passages.extend(doc.passages)

    assert any([expected_content in p.text for p in all_passages])
