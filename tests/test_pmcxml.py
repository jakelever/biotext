from io import StringIO

import bioc
import pytest

from bioconverters.main import docs2bioc
from bioconverters.utils import TABLE_DELIMITER, TextChunk

from .util import fetch_xml


@pytest.fixture(scope='module')
def table_article():
    article = fetch_xml('PMC3203921', 'pmc')  # has a table to be processed in it
    return article


@pytest.fixture(scope='module')
def formula_article():
    article = fetch_xml('PMC2939780', 'pmc')
    return article


@pytest.fixture(scope='module')
def citation_offset_article():
    article = fetch_xml('PMC8466798', 'pmc')
    return article


def test_convert_pmc_with_table(table_article):
    file = StringIO(table_article)
    table_header = (
        'ERBB2 mutation\tExon\tFunctional region\tCancer type\tLapatinib\tAEE788\tReference'
    )
    expected_content = "WT\tNA\tNA\tBreast cancer\t30\t257\tNA\tL755S\t19\tATP binding region\tBreast and gastric cancer\t>2000\t897\t4\tL755P	19\tATP binding region\tNSCLC\t1545\t1216\t2,3\tV773A\t20\tATP binding region\tSCCHN\t146\t200\t6\tV777L\t20\tATP binding region\tGastric, colon and lung\t27\t215\t3,4\tT798M\t20\tGate keeper residue\tNA\t1433\t>2000\tNA\tN857S\t21\tActivation loop\tOvarian cancer\t75\t246\t2\tT862A\t21\tActivation loop\tPrimary gastric cancer\t125\t191\t7\tH878Y\t21\tActivation loop\tHepatocellular carcinoma\t14\t168\t5"
    all_passages = []
    for doc in docs2bioc(file, 'pmcxml', trim_sentences=False, all_xml_path_infon=True):
        all_passages.extend(doc.passages)
    table_body = [p.text for p in all_passages if 'tbody' in p.infons.get('xml_path', '')]
    assert len(table_body) == 1
    assert len(table_body[0].split(TABLE_DELIMITER)) == len(expected_content.split(TABLE_DELIMITER))
    assert table_body[0].split(TABLE_DELIMITER) == expected_content.split(TABLE_DELIMITER)
    assert table_header in [p.text for p in all_passages if 'thead' in p.infons.get('xml_path', '')]


def test_custom_tag_handler(table_article):
    expected_content = 'SOME DUMMY CAPTION TEXT'
    all_passages = []
    file = StringIO(table_article)

    def dummy_handler(elem, custom_handlers):
        return [TextChunk(expected_content, None, '')]

    for doc in docs2bioc(file, 'pmcxml', tag_handlers={'caption': dummy_handler}):
        all_passages.extend(doc.passages)

    assert any([expected_content in p.text for p in all_passages])


def test_sibling_intext_citations(table_article):
    all_passages = []
    all_annotations = []
    file = StringIO(table_article)

    for doc in docs2bioc(file, 'pmcxml', trim_sentences=False, mark_citations=True):
        all_passages.extend(doc.passages)
        all_annotations.extend([a.annotation for a in bioc.annotations(doc)])

    for chunk in all_passages:
        if 'PyMOL' in chunk.text:
            break
    assert any(
        ['inspected using the graphics program PyMOL.' in chunk.text for chunk in all_passages]
    )
    assert '[14],[16],[23]\u2013[25]' in [a.infons['citation_text'] for a in all_annotations]


def test_citation_offset(citation_offset_article):
    # https://github.com/jakelever/biotext/issues/9
    file = StringIO(citation_offset_article)
    list(docs2bioc(file, 'pmcxml', trim_sentences=False, mark_citations=True))
