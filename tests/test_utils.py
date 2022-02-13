import textwrap
import xml.etree.cElementTree as etree
from typing import List, Optional
from unittest.mock import MagicMock
from xml.sax.saxutils import escape

import pytest
from bioconverters.utils import (
    TABLE_DELIMITER,
    cleanup_text,
    extract_text_chunks,
    merge_adjacent_xref_siblings,
    remove_brackets_without_words,
    strip_annotation_markers,
)
from hypothesis import given, infer
from hypothesis import strategies as st

from .util import data_file_path


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
        ('   }{ \t}{   ', '   }{ \t}{   '),
        ('( [] [ ] )', ''),
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
    assert '1' in annotations_map.values()
    assert '2,3' in annotations_map.values()
    for key in annotations_map:
        assert key in full_text
    final_text, annotations_result = strip_annotation_markers(full_text, annotations_map)
    assert final_text == expected

    locations = []
    text = []
    for ann in annotations_result:
        text.append(ann.text)
        for loc in ann.locations:
            locations.append(loc.offset)
    assert text == ['', '']
    assert locations == [113, 325]


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
            [42],
        ),
        (
            'This is a sentence with an in-text citation ANN_1234 that has multiple references in the same sentence ANN_1235.',
            {'ANN_1234': 'Blargh, M. et. al, 2000', 'ANN_1235': 'Som other blargh, 2001'},
            'This is a sentence with an in-text citation that has multiple references in the same sentence.',
            [42, 92],
        ),
        (
            'This is a sentence with an in-text citation ANN_1234. In an inner sentence',
            {'ANN_1234': 'Blargh, M. et. al, 2000'},
            'This is a sentence with an in-text citation. In an inner sentence',
            [42],
        ),
        (
            'This is a sentence with an in-text citation (ANN_1234).',
            {'ANN_1234': 'Blargh, M. et. al, 2000'},
            'This is a sentence with an in-text citation.',
            [42],
        ),
        (
            'This is a sentence with an in-text citation [ANN_1234].',
            {'ANN_1234': 'Blargh, M. et. al, 2000'},
            'This is a sentence with an in-text citation.',
            [42],
        ),
    ],
    ids=[
        'single citation',
        'multiple citations',
        'middle sentence citation',
        'round-brackets',
        'square-brackets',
    ],
)
def test_strip_annotation_markers(text, annotations_map, expected_text, expected_locations):
    text_result, annotations_result = strip_annotation_markers(
        text, annotations_map, marker_pattern=r'ANN_\d+'
    )
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


@pytest.mark.parametrize('xml_file,rows,cols', [('format_chars_table.xml', 1, 2)])
def test_extract_explicit_table(xml_file, rows, cols):
    with open(data_file_path(xml_file), 'r') as fh:
        table_xml = fh.read()

    chunks = extract_text_chunks([etree.fromstring(table_xml.strip())])

    table_header = [c.text for c in chunks if c.xml_path.endswith('thead')]

    assert len(table_header) == 1
    assert len(table_header[0].split(TABLE_DELIMITER)) == cols

    table_body = [c.text for c in chunks if c.xml_path.endswith('tbody')]
    assert len(table_body) == 1
    assert len(table_body[0].split(TABLE_DELIMITER)) == cols * rows


def test_floating_table():
    xml_input = data_file_path('floating_table.xml')
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
        ('   }{ \t}{   ', '}{\t}{'),
    ],
)
def test_cleanup_text(input, output):
    assert cleanup_text(input) == output


@given(text=infer, sibling_text=infer, sibling_tail=infer)
def test_merge_adjacent_xref_siblings(
    text: Optional[str], sibling_text: Optional[str], sibling_tail: Optional[str]
):
    tail = ', '
    merged = merge_adjacent_xref_siblings(
        [
            MagicMock(text=text, tail=tail, attrib={'ref-type': 'thing'}, tag='xref'),
            MagicMock(
                text=sibling_text, tail=sibling_tail, attrib={'ref-type': 'thing'}, tag='xref'
            ),
        ]
    )
    assert len(merged) == 1

    merged = merge_adjacent_xref_siblings(
        [
            MagicMock(text=text, tail='a', attrib={'ref-type': 'thing'}, tag='xref'),
            MagicMock(
                text=sibling_text, tail=sibling_tail, attrib={'ref-type': 'thing'}, tag='xref'
            ),
        ]
    )
    assert len(merged) == 2


def test_keep_extlink_supplementary():
    xml = textwrap.dedent(
        '''\
        <?xml version="1.1" encoding="utf8" ?>
         <article xmlns:ali="http://www.niso.org/schemas/ali/1.0/"
            xmlns:xlink="http://www.w3.org/1999/xlink"
            xmlns:mml="http://www.w3.org/1998/Math/MathML" article-type="research-article">
            <p>
                Introduction of the <italic>NTRK3</italic> G623R mutation to the <italic>ETV6-NTRK3</italic> construct (Ba/F3-ETV6-NTRK3 G623R) conferred reduced sensitivity to entrectinib, increasing the IC<sub>50</sub> value in the proliferation assays more than 250-fold (2 to 507 nM) relative to the Ba/F3-ETV6-NTRK3 cells (Figure <xref ref-type="fig" rid="MDW042F3">3</xref>E). The <italic>NTRK3</italic> G623R mutation conferred even greater loss of sensitivity to the other tested Trk inhibitors, TSR-011 (Tesaro) and LOXO-101 (LOXO), eliciting IC<sub>50</sub> proliferation values of &gt;1000 nM (<ext-link ext-link-type="uri" xlink:href="http://annonc.oxfordjournals.org/lookup/suppl/doi:10.1093/annonc/mdw042/-/DC1">supplementary Figure S4C, available at <italic>Annals of Oncology</italic> online</ext-link>).
            </p>
        </article>'''
    )
    chunks = extract_text_chunks([etree.fromstring(xml)])
    assert len(chunks) == 1
    chunk = chunks[0].text
    print(chunk)
    assert '(supplementary Figure S4C, available at Annals of Oncology online)' in chunk


def test_drops_extlink_urls():
    xml = textwrap.dedent(
        '''\
    <?xml version="1.1" encoding="utf8" ?>
    <article xmlns:ali="http://www.niso.org/schemas/ali/1.0/"
        xmlns:xlink="http://www.w3.org/1999/xlink"
        xmlns:mml="http://www.w3.org/1998/Math/MathML" article-type="research-article">
    <p>
        Crystal  Protein Data Bank (
        <ext-link ext-link-type="uri" xlink:href="http://www.pdb.org">www.pdb.org</ext-link>
        ). Crystal structures of complexes with  program PyMOL (
        <ext-link ext-link-type="uri" xlink:href="http://www.pymol.org">www.pymol.org</ext-link>
        )
        <xref rid="pone.0026760-Yun1" ref-type="bibr">[14]</xref>
        ,
        <xref rid="pone.0026760-Yun2" ref-type="bibr">[16]</xref>
        ,
        <xref rid="pone.0026760-Stamos1" ref-type="bibr">[23]</xref>
        –
        <xref rid="pone.0026760-Qiu1" ref-type="bibr">[25]</xref>
        .
    </p>
    </article>'''
    )
    chunks = extract_text_chunks([etree.fromstring(xml)])
    assert len(chunks) == 1
    chunk = chunks[0].text
    print(chunk)
    assert 'program PyMOL.' in chunk
    assert '[14]' not in chunk
    assert '//www.' not in chunk
