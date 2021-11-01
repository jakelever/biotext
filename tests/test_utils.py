import os
import xml.etree.cElementTree as etree
from typing import List
from xml.sax.saxutils import escape

import pytest
from bioconverters.utils import (
    TABLE_DELIMITER,
    cleanup_text,
    extract_text_chunks,
    remove_brackets_without_words,
    strip_annotation_markers,
)
from hypothesis import given
from hypothesis import strategies as st


@pytest.mark.parametrize(
    'test_input,expected',
    [
        (' ((())(', ' ('),
        ('( [3] [4] )', '( [3] [4] )'),
        ('( [] )', ''),
        ('(Fig. 1)', '(Fig. 1)'),
        ('(Table. 1)', '(Table. 1)'),
        ('( ; )', ''),
        ('( . )', ''),
    ],
)
def test_remove_brackets_without_words(test_input, expected):
    assert expected == remove_brackets_without_words(test_input)


def test_extract_text_chunks_sibling_xrefs():
    siblings_example = """<article><abstract><p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Duis nec diam sed nisl aliquam scelerisque quis at turpis <xref ref-type="bibr">1</xref>. Vestibulum urna quam, accumsan id efficitur eget, fermentum vel eros. Pellentesque nisi urna, fringilla vitae sapien a, eleifend tempus libero. Nullam eget porta velit. Praesent bibendum dolor enim, ac lobortis<xref ref-type="bibr">2</xref>,            <xref ref-type="bibr">3</xref>.</p></abstract></article>"""
    expected = """Lorem ipsum dolor sit amet, consectetur adipiscing elit. Duis nec diam sed nisl aliquam scelerisque quis at turpis. Vestibulum urna quam, accumsan id efficitur eget, fermentum vel eros. Pellentesque nisi urna, fringilla vitae sapien a, eleifend tempus libero. Nullam eget porta velit. Praesent bibendum dolor enim, ac lobortis."""

    root_nodes = [etree.fromstring(siblings_example)]
    annotations_map = {}
    chunks = extract_text_chunks(root_nodes, annotations_map=annotations_map)
    full_text = ' '.join(c.text for c in chunks if c.text.strip())
    print(full_text)
    assert '1' in annotations_map.values()
    assert '2, 3' in annotations_map.values()
    for key in annotations_map:
        assert key in full_text
    final_text, annotations_result = strip_annotation_markers(full_text, annotations_map)
    print(final_text)
    assert final_text == expected

    locations = []
    text = []
    for ann in annotations_result:
        text.append(ann.text)
        for loc in ann.locations:
            locations.append(loc.offset)
    assert text == ['turpis', 'lobortis']
    assert locations == [108, 318]


def test_extract_figure_label():
    xml_input = '<article><fig id="pone-0026760-g003" position="float"><object-id pub-id-type="doi">10.1371/journal.pone.0026760.g003</object-id><label>Figure 3</label><caption><title>Anchorage-independent growth of ERBB2 mutants.</title></caption><graphic/></fig></article>'
    root_nodes = [etree.fromstring(xml_input)]
    annotations_map = {}
    chunks = extract_text_chunks(root_nodes, annotations_map=annotations_map)
    assert not annotations_map
    xml_paths = [c.xml_path for c in chunks]
    assert 'article/fig/label' in xml_paths
    assert 'Figure 3' in [c.text for c in chunks if c.xml_path == 'article/fig/label']


@pytest.mark.parametrize(
    'text,annotations_map,expected_text,expected_locations',
    [
        (
            'This is a sentence with an in-text citation ANN_1234.',
            {'ANN_1234': 'Blargh, M. et. al, 2000'},
            'This is a sentence with an in-text citation.',
            [35],
        ),
        (
            'This is a sentence with an in-text citation ANN_1234 that has multiple references in the same sentence ANN_1235.',
            {'ANN_1234': 'Blargh, M. et. al, 2000', 'ANN_1235': 'Som other blargh, 2001'},
            'This is a sentence with an in-text citation that has multiple references in the same sentence.',
            [35, 85],
        ),
        (
            'This is a sentence with an in-text citation ANN_1234. In an inner sentence',
            {'ANN_1234': 'Blargh, M. et. al, 2000'},
            'This is a sentence with an in-text citation. In an inner sentence',
            [35],
        ),
        (
            'This is a sentence with an in-text citation (ANN_1234).',
            {'ANN_1234': 'Blargh, M. et. al, 2000'},
            'This is a sentence with an in-text citation.',
            [35],
        ),
    ],
    ids=['single citation', 'multiple citations', 'middle sentence citation', 'brackets'],
)
def test_strip_annotation_markers(text, annotations_map, expected_text, expected_locations):
    text_result, annotations_result = strip_annotation_markers(text, annotations_map)
    assert text_result == expected_text
    locations = []
    for ann in annotations_result:
        for loc in ann.locations:
            locations.append(loc.offset)
    assert locations == expected_locations


def test_extract_title_with_italics():
    xml = '<article><article-title>Activating mutations in <italic>ALK</italic> provide a therapeutic target in neuroblastoma</article-title></article>'
    chunks = extract_text_chunks([etree.fromstring(xml)])
    assert len(chunks) == 1
    assert (
        'Activating mutations in ALK provide a therapeutic target in neuroblastoma'
        == chunks[0].text
    )


@given(
    values=st.lists(
        st.text(alphabet=st.characters(blacklist_categories=['Cc', 'Cs'])), min_size=1, max_size=50
    ),
    rows=st.integers(min_value=1, max_value=3),
    cols=st.integers(min_value=1, max_value=3),
)
def test_extract_delimited_table(values: List[str or int or float or None], rows: int, cols: int):
    values = [escape(v) for v in values]
    rows_xml = []
    values_used = set()

    for row_index in range(rows):
        tr = []
        for col_index in range(cols):
            value = values[(row_index * col_index + col_index) % len(values)]
            tr.append(
                f'\n<td rowspan="1" colspan="1" id="cell_{row_index}_{col_index}">{value}</td>'
            )
            values_used.add(value)
        rows_xml.append('\n<tr>' + "".join(tr) + '\n</tr>')

    table_body_xml = '<tbody>' + "".join(rows_xml) + '\n</tbody>'

    thead = []
    for col_index in range(cols):
        thead.append(f'<td rowspan="1" colspan="1">Column {col_index}</td>')
    table_header_xml = '<thead><tr>' + "".join(thead) + '</tr></thead>'

    table_xml = f'''
    <?xml version="1.1" encoding="utf8" ?>
    <article><table-wrap>
        <object-id pub-id-type="doi">some doi url</object-id>
        <label>Table 1</label>
        <caption>
            <title>The title of the table</title>
        </caption>
        <alternatives>
            <graphic />
            <table frame="hsides" rules="groups">
            {table_header_xml}
            {table_body_xml}
            </table>
        </alternatives>
        <table-wrap-foot>
            <fn>
            <label/>
            <p>some long description of the table contents in the table footer
            </p>
            </fn>
        </table-wrap-foot>
    </table-wrap></article>
    '''
    chunks = extract_text_chunks([etree.fromstring(table_xml.strip())])

    table_header = [c.text for c in chunks if c.xml_path.endswith('thead')]

    assert len(table_header) == 1
    assert len(table_header[0].split(TABLE_DELIMITER)) == cols

    table_body = [c.text for c in chunks if c.xml_path.endswith('tbody')]

    if cols == 1 and rows == 1 and all([cleanup_text(v) == '' for v in values_used]):
        # will omit the table body if it is entirely empty
        assert not table_body
    else:
        assert len(table_body) == 1
        assert len(table_body[0].split(TABLE_DELIMITER)) == cols * rows


def test_floating_table():
    xml_input = os.path.join(os.path.dirname(__file__), 'data', 'floating_table.xml')
    with open(xml_input, 'r') as fh:
        xml_data = fh.read()
    chunks = extract_text_chunks([etree.fromstring(xml_data)])
    expected_columns = 6
    expected_rows = 16

    table_header = [c.text for c in chunks if c.xml_path.endswith('thead')]

    assert len(table_header) == 1
    header = table_header[0].split(TABLE_DELIMITER)
    assert header == ['Patient sample', 'Exon', 'DNA', 'Protein', 'Domain', 'Germline/ Somatic']

    table_body = [c.text for c in chunks if c.xml_path.endswith('tbody')]
    assert len(table_body) == 1
    assert len(table_body[0].split(TABLE_DELIMITER)) == expected_columns * expected_rows


@pytest.mark.parametrize(
    'input,output',
    [
        (
            'some words with a sentence . that has an unnecessary space in the middle.',
            'some words with a sentence. that has an unnecessary space in the middle.',
        ),
        ('extra space , before comma', 'extra space, before comma'),
        ('extra space ; before semi-colon', 'extra space; before semi-colon'),
    ],
)
def test_cleanup_text(input, output):
    assert cleanup_text(input) == output
