import xml.etree.cElementTree as etree
from typing import List
from xml.sax.saxutils import escape

import pytest
from hypothesis import given
from hypothesis import strategies as st

from bioconverters.utils import TABLE_DELIMITER, cleanup_text, extract_text_chunks

from .util import data_file_path


@given(
    values=st.lists(
        st.text(alphabet=st.characters(blacklist_categories=["Cc", "Cs"])),
        min_size=1,
        max_size=50,
    ),
    rows=st.integers(min_value=1, max_value=3),
    cols=st.integers(min_value=1, max_value=3),
)
def test_extract_delimited_table(
    values: List[str or int or float or None], rows: int, cols: int
):
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
        rows_xml.append("\n<tr>" + "".join(tr) + "\n</tr>")

    table_body_xml = "<tbody>" + "".join(rows_xml) + "\n</tbody>"

    thead = []
    for col_index in range(cols):
        thead.append(f'<td rowspan="1" colspan="1">Column {col_index}</td>')
    table_header_xml = "<thead><tr>" + "".join(thead) + "</tr></thead>"

    table_xml = f"""
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
    """
    chunks = extract_text_chunks([etree.fromstring(table_xml.strip())])

    table_header = [c.text for c in chunks if c.xml_path.endswith("thead")]

    assert len(table_header) == 1
    assert len(table_header[0].split(TABLE_DELIMITER)) == cols

    table_body = [c.text for c in chunks if c.xml_path.endswith("tbody")]

    if cols == 1 and rows == 1 and all([cleanup_text(v) == "" for v in values_used]):
        # will omit the table body if it is entirely empty
        assert not table_body
    else:
        assert len(table_body) == 1
        assert len(table_body[0].split(TABLE_DELIMITER)) == cols * rows


# TODO: tests for this table https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7461630/table/T2/?report=objectonly
# need to care about indenting


@pytest.mark.parametrize(
    "filename,expected_chunks",
    [
        [
            "table_colspan_dividers.xml",
            ["Sex: Female", "Sex: Male", "Race: White", "Race: Asian", "Race: Other"],
        ],
        ["table_multi_level_header.xml", ["L130V\tALTERED\t"]],
        [
            "table_rowspans.xml",
            ["SUP-CR500-2\tI1171S\tI1171T\tNPM-ALK ALCL\tCrizotinib-R"],
        ],
        ["table_inner_colspan.xml", ["months\t30.5\t30.5\t16.8"]],
        ["table.xml", ["TCGA-BR-4370-01\tStomach (TCGA)\tR2193C"]],
    ],
)
def test_parses_table_body(filename, expected_chunks):
    xml_input = data_file_path(filename)
    with open(xml_input, "r") as fh:
        xml_data = fh.read()
    chunks = extract_text_chunks([etree.fromstring(xml_data)])
    table_body = [c.text for c in chunks if c.xml_path.endswith("tbody")]

    for chunk in expected_chunks:
        assert chunk in table_body[0]


@pytest.mark.parametrize(
    "filename,expected_header",
    [
        [
            "table_multi_level_header.xml",
            [
                "p53 MUTATION",
                "FUNCTIONAL a STATUS",
                "IARC DATABASE b SOMATIC TOTAL",
                "IARC DATABASE b SOMATIC BREAST",
                "IARC DATABASE b GERMLINE FAMILIES",
                "FEATURES c\n",
            ],
        ],
        [
            "table_floating.xml",
            [
                "Patient sample",
                "Exon",
                "DNA",
                "Protein",
                "Domain",
                "Germline/ Somatic\n",
            ],
        ],
    ],
)
def test_parses_table_header(filename, expected_header):
    xml_input = data_file_path(filename)
    with open(xml_input, "r") as fh:
        xml_data = fh.read()
    chunks = extract_text_chunks([etree.fromstring(xml_data)])
    table_header = [c.text for c in chunks if c.xml_path.endswith("thead")][0].split(
        TABLE_DELIMITER
    )
    assert table_header == expected_header


@pytest.mark.parametrize(
    "filename,table_number,expected_columns,expected_rows",
    [
        ("table_floating.xml", 0, 6, 16),
        ("table_format_chars.xml", 0, 1, 2),
        ("table_colspan_dividers.xml", 0, 2, 37),
        ("table_rowspans.xml", 0, 6, 29),
        ("table_malformed_span.xml", 0, 14, 3),
        ("table_inner_colspan.xml", 0, 4, 8),
        ("table.xml", 0, 3, 79),
        ("PMC6580637.xml", 0, 5, 12),
        ("PMC6580637.xml", 1, 6, 4),
        ("PMC6580637.xml", 2, 8, 6),
    ],
)
def test_parses_table_body_size(
    filename, table_number, expected_columns, expected_rows
):
    xml_input = data_file_path(filename)
    with open(xml_input, "r") as fh:
        xml_data = fh.read()
    chunks = extract_text_chunks([etree.fromstring(xml_data)])

    table_body = [c.text for c in chunks if c.xml_path.endswith("tbody")]
    assert len(table_body) > table_number
    table_body = table_body[table_number]
    assert len(table_body.split(TABLE_DELIMITER)) == expected_columns * expected_rows
