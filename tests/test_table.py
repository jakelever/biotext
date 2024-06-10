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
    "filename,expected_header,table_index",
    [
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
            0,
        ],
        [
            "PMC5029658.xml",
            [
                "",
                "",
                "Cell Line SUP-M2 IC50",
                "Cell Line SUP-M2 Fold Change",
                "Cell Line SU-DHL-1 IC50",
                "Cell Line SU-DHL-1 Fold Change",
                "Cell Line I1171S SUP-CR500-2 IC50",
                "Cell Line I1171S SUP-CR500-2 Fold Change",
                "Cell Line F1174L SUP-LR150-2 IC50",
                "Cell Line F1174L SUP-LR150-2 Fold Change",
                "Cell Line R1192P DHL1-CR500 IC50",
                "Cell Line R1192P DHL1-CR500 Fold Change",
                "Cell Line T1151M DHL1-LR150 IC50",
                "Cell Line T1151M DHL1-LR150 Fold Change",
                "Cell Line G1269A DHL1-CR500-2 IC50",
                "Cell Line G1269A DHL1-CR500-2 Fold Change\n",
            ],
            1,
        ],
    ],
)
def test_parses_table_header(filename, expected_header, table_index):
    xml_input = data_file_path(filename)
    with open(xml_input, "r") as fh:
        xml_data = fh.read()
    chunks = extract_text_chunks([etree.fromstring(xml_data)])
    table_header = [c.text for c in chunks if c.xml_path.endswith("thead")]
    assert len(table_header) > table_index
    table_header = table_header[table_index]
    table_header = table_header.split(TABLE_DELIMITER)
    assert table_header == expected_header


@pytest.mark.parametrize(
    "filename,table_index,expected_columns,expected_rows",
    [
        ("table_floating.xml", 0, 6, 16),
        ("table_format_chars.xml", 0, 1, 2),
        ("table_rowspans.xml", 0, 6, 29),
        ("table_malformed_span.xml", 0, 14, 3),
        ("table_inner_colspan.xml", 0, 4, 8),
        ("table.xml", 0, 3, 79),
        ("PMC6580637.xml", 0, 5, 12),
        ("PMC6580637.xml", 1, 6, 4),
        ("PMC6580637.xml", 2, 8, 6),
    ],
)
def test_parses_table_body_size(filename, table_index, expected_columns, expected_rows):
    xml_input = data_file_path(filename)
    with open(xml_input, "r") as fh:
        xml_data = fh.read()
    chunks = extract_text_chunks([etree.fromstring(xml_data)])

    table_body = [c.text for c in chunks if c.xml_path.endswith("tbody")]
    assert len(table_body) > table_index
    table_body = table_body[table_index]
    assert len(table_body.split(TABLE_DELIMITER)) == expected_columns * expected_rows


@pytest.mark.parametrize(
    "filename,table_index,row_index,row_content",
    [
        (
            "PMC5029658.xml",
            0,
            5,
            ["SUP-CR500-2", "I1171S", "I1171N", "EML4-ALK NSCLC", "Alectinib-R", ""],
        ),  # rowspans split
        pytest.param(
            "PMC4816447.xml",
            0,
            2,
            ["19", "c.2236_2250del", "p.Glu746_Ala750del", "3 (360x)", "yes/yes"],
            marks=pytest.mark.skip(reason="TODO"),
        ),
        (
            "PMC4919728.xml",
            0,
            1,
            ["Age at diagnosis (year): Median", "31.4", "5.1", "36.7", "6.8"],
        ),
    ],
)
def test_parses_table_body_row_content(filename, table_index, row_index, row_content):
    xml_input = data_file_path(filename)
    with open(xml_input, "r") as fh:
        xml_data = fh.read()
    chunks = extract_text_chunks([etree.fromstring(xml_data)])

    table_body = [c.text for c in chunks if c.xml_path.endswith("tbody")]
    assert len(table_body) > table_index
    table_body = table_body[table_index]
    assert len(table_body) > row_index

    columns = len(row_content)

    row = table_body.split(TABLE_DELIMITER)[
        row_index * columns : (row_index + 1) * columns
    ]
    assert row == row_content
