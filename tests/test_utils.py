import textwrap
import xml.etree.cElementTree as etree
from typing import List, Optional
from unittest.mock import MagicMock
from xml.sax.saxutils import escape

import pytest
from hypothesis import given, infer
from hypothesis import strategies as st

from bioconverters.utils import (
    TABLE_DELIMITER,
    cleanup_text,
    extract_text_chunks,
    merge_adjacent_xref_siblings,
    remove_brackets_without_words,
    strip_annotation_markers,
)

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


PARSING_CASES = [
    ['incubator containing 5% CO<sub>2</sub>', 'incubator containing 5% CO2'],
    [
        '<article-title>Activating mutations in <italic>ALK</italic> provide a therapeutic target in neuroblastoma</article-title>',
        'Activating mutations in ALK provide a therapeutic target in neuroblastoma',
    ],
    ['10<sup>4</sup>', '10^4'],
    ['especially in <italic>CBL</italic>-W802* cells', 'especially in CBL-W802* cells'],
    [
        'influenced by the presence of allelic variants&#x2014;GSTP1 Ile<sub>105</sub>Val (rs1695) and <italic>GSTP1</italic> Ala<sub>114</sub>Val (rs1138272), with homozygote',
        'influenced by the presence of allelic variants--GSTP1 Ile105Val (rs1695) and GSTP1 Ala114Val (rs1138272), with homozygote',
    ],
    [
        '''breast cancer, clear cell renal carcinoma, and colon cancer<xref ref-type="bibr" rid="b6">6</xref>
        <xref ref-type="bibr" rid="b7">7</xref>
        <xref ref-type="bibr" rid="b8">8</xref>
        <xref ref-type="bibr" rid="b9">9</xref>
        <xref ref-type="bibr" rid="b10">10</xref> have successfully identified''',
        'breast cancer, clear cell renal carcinoma, and colon cancer have successfully identified',
    ],
    ['Label<xref ref-type="table-fn" rid="GENE">a</xref>', 'Label a'],
    [
        'Introduction of the <italic>NTRK3</italic> G623R mutation',
        'Introduction of the NTRK3 G623R mutation',
    ],
    ['Patient<break/>sample', 'Patient sample'],
    [
        ''', and in the transgenic
GATA-1,
<sup>low</sup> mouse''',
        ', and in the transgenic GATA-1, low mouse',
    ],
    [
        'we selected an allele (designated <italic>cic</italic><sup><italic>4</italic></sup>) that removes',
        'we selected an allele (designated cic^4) that removes',
    ],
    [
        'whereas a CIC derivative lacking the HMG-box is mainly cytoplasmic [<xref rid="pgen.1006622.ref009" ref-type="bibr">9</xref>], implying',
        'whereas a CIC derivative lacking the HMG-box is mainly cytoplasmic, implying',
    ],
    [
        'inactivated by somatic mutations [<xref rid="pgen.1006622.ref022" ref-type="bibr">22</xref>&#x2013;<xref rid="pgen.1006622.ref030" ref-type="bibr">30</xref>], but',
        'inactivated by somatic mutations, but',
    ],
    [
        'regulation of the Wnt-&#x3B2;-catenin pathway',
        'regulation of the Wnt-beta-catenin pathway',
    ],
    [
        'previously reported cell lines (CAL27, CAL33, Detroit 562, UM-SCC-47, SCC-25, SCC-9, UM-SCC-11B and UM-SCC-17B) [<xref rid="R6" ref-type="bibr">6</xref>], while',
        'previously reported cell lines (CAL27, CAL33, Detroit 562, UM-SCC-47, SCC-25, SCC-9, UM-SCC-11B and UM-SCC-17B), while',
    ],
    [
        'clinic-pathologic parameters, &#x3C7;2 and Fisher exact tests',
        'clinic-pathologic parameters, chi2 and Fisher exact tests',
    ],
    [
        'due to RB1 inhibition [<xref rid="R38" ref-type="bibr">38</xref>], the specific',
        'due to RB1 inhibition, the specific',
    ],
    # TODO: discuss with jake best moves for cases below
    [
        'the specific HPV<sup>+</sup> gene expression',
        'the specific HPV+ gene expression',
    ],
    [
        'known to be resistant to 1<sup>st</sup> and 2<sup>nd</sup> generation EGFR-TKIS, osimertinib',
        'known to be resistant to 1st and 2nd generation EGFR-TKIS, osimertinib',
    ],
    [
        'at 37&#xB0;C in a humidified 5% CO<sub>2</sub> incubator',
        'at 37 deg C in a humidified 5% CO2 incubator',
    ],
    [
        'seeded at concentrations below 1 &#xD7; 10<sup>6</sup>/ml, selected',
        'seeded at concentrations below 1 x 10^6/ml, selected',
    ],
    [
        'PCR cycling parameters were: one cycle of 95 &#xB0;C for 15 min; 35 cycles of 95 &#xB0;C for 20 s, 60 &#xB0;C for 30 s, and 72 &#xB0;C for 1 min; followed by one cycle of 72 &#xB0;C for 3 min.',
        'PCR cycling parameters were: one cycle of 95 deg C for 15 min; 35 cycles of 95 deg C for 20 s, 60 deg C for 30 s, and 72 deg C for 1 min; followed by one cycle of 72 deg C for 3 min.',
    ],
    [
        '9 patients with a <italic>BRAF</italic>-mutant tumour',
        '9 patients with a BRAF-mutant tumour',
    ],
    [
        'patients with <italic>BRAF</italic><sup>WT</sup> tumours',
        'patients with BRAF-WT tumours',
    ],
    ['MSI<sup>hi</sup> tumours', 'MSI-hi tumours'],
    ['P53<break/>mutation', 'P53 mutation'],
    [
        'upper limit of normal, creatinine clearance &#x2A7E;30&#x2009;ml&#x2009;min<sup>&#x2212;1</sup>,',
        'upper limit of normal, creatinine clearance ⩾30 ml min^-1,',
    ],
    ['<italic>P</italic> = 1.0 &#xD7; 10<sup>&#x2212;6</sup>', 'P = 1.0 x 10^-6'],
    [
        'domains <xref rid="pone.0032514-McEwan1" ref-type="bibr">[13]</xref>: the N-terminal domain',
        'domains: the N-terminal domain',
    ],
    [
        'motif (residues 234 to 247 <xref rid="pone.0032514-Betney1" ref-type="bibr">[56]</xref>) immediately',
        'motif (residues 234 to 247) immediately',
    ],
    [
        'the oncometabolite R(&#x2013;)-2-hydroxyglutarate at the',
        'the oncometabolite R(-)-2-hydroxyglutarate at the',
    ],
    ['[<sup>3</sup>H]-Thymidine', '[3H]-Thymidine'],
    [
        '<p id="P10">Class IA PI3K dimers are composed of a p110 catalytic subunit and a p85 regulatory subunit, each with three isoforms encoded by three genes<sup><xref rid="R17" ref-type="bibr">17</xref></sup>. Mutations in five of these genes have been observed in many human cancers<sup><xref rid="R31" ref-type="bibr">31</xref>&#x2013;<xref rid="R34" ref-type="bibr">34</xref></sup>. Our data show that mutations in the p85&#x3B2; (<italic>PIK3R2</italic>) regulatory and p110&#x3B1; (<italic>PIK3CA</italic>) catalytic subunits are a common cause of megalencephaly syndromes, albeit with a clear genotype-phenotype correlation as <italic>PIK3R2</italic> and <italic>PIK3CA</italic> mutations are associated with MPPH (<italic>P</italic> = 3.3 &#xD7; 10<sup>&#x2212;6</sup>) and MCAP (<italic>P</italic> = 1.0 &#xD7; 10<sup>&#x2212;6</sup>), respectively (<xref rid="SD1" ref-type="supplementary-material">Supplementary Table 9</xref>, <xref rid="SD1" ref-type="supplementary-material">Online Methods</xref>). Both <italic>PIK3R1</italic> and <italic>PIK3R2</italic> have oncogenic potential, and mutations including the glycine-to-arginine substitution of <italic>PIK3R2</italic> found in MPPH (p.Gly373Arg) and substitution of the homologous amino acid residue in <italic>PIK3R1</italic> (p.Gly376Arg) have been found in cancer<sup><xref rid="R32" ref-type="bibr">32</xref></sup>. Available functional studies showed that several of these mutations disrupt the inactive conformation of the PI3K dimer and maintain the catalytic subunit in a high activity state<sup><xref rid="R32" ref-type="bibr">32</xref>,<xref rid="R35" ref-type="bibr">35</xref></sup>. Our observations in lymphoblastoid cells derived from patient LR00-016a1 show that the p.Gly373Arg mutation results in increased PI3K activity and elevated PI3K-mTOR signaling, further supporting this mechanism.</p>',
        'Class IA PI3K dimers are composed of a p110 catalytic subunit and a p85 regulatory subunit, each with three isoforms encoded by three genes. Mutations in five of these genes have been observed in many human cancers. Our data show that mutations in the p85beta (PIK3R2) regulatory and p110alpha (PIK3CA) catalytic subunits are a common cause of megalencephaly syndromes, albeit with a clear genotype-phenotype correlation as PIK3R2 and PIK3CA mutations are associated with MPPH (P = 3.3 x 10^-6) and MCAP (P = 1.0 x 10^-6), respectively (Supplementary Table 9,Online Methods). Both PIK3R1 and PIK3R2 have oncogenic potential, and mutations including the glycine-to-arginine substitution of PIK3R2 found in MPPH (p.Gly373Arg) and substitution of the homologous amino acid residue in PIK3R1 (p.Gly376Arg) have been found in cancer. Available functional studies showed that several of these mutations disrupt the inactive conformation of the PI3K dimer and maintain the catalytic subunit in a high activity state. Our observations in lymphoblastoid cells derived from patient LR00-016a1 show that the p.Gly373Arg mutation results in increased PI3K activity and elevated PI3K-mTOR signaling, further supporting this mechanism.',
    ],
    [
        '<p>The AR, like other members of the steroid hormone receptor family, is a ligand-activated transcription factor which has distinct structural and functional domains <xref rid="pone.0032514-McEwan1" ref-type="bibr">[13]</xref>: the N-terminal domain (NTD) important for transactivation; the DNA binding domain (DBD) and the C-terminal ligand binding domain (LBD). Upon ligand binding, the AR undergoes conformational transformation facilitating intra- and intermolecular interactions <xref rid="pone.0032514-Centenera1" ref-type="bibr">[14]</xref>. The transactivational capability of the AR is modulated by several signaling systems <xref rid="pone.0032514-Reddy1" ref-type="bibr">[15]</xref> through a range of post-translational modifications <xref rid="pone.0032514-McEwan1" ref-type="bibr">[13]</xref>, <xref rid="pone.0032514-Koochekpour1" ref-type="bibr">[16]</xref>. Although the AR exerts most of its actions by functioning as a transcription factor binding to specific response elements, non-genomic effects can also contribute to the regulatory outcome. Activation of the phosphatidylinositol 3-kinase (PI3K)/Akt signaling pathway not only regulates AR activity through phosphorylation of the receptor, but also has a major role in the process leading to invasion and metastasis of PCa cells through downstream phosphorylation of affiliated substrates leading to protection from apoptosis and increased cell survival. The AR can stimulate PI3K/Akt signaling by interacting directly with the p85&#x3B1; regulatory subunit of PI3K in response to synthetic and natural androgens <xref rid="pone.0032514-Baron1" ref-type="bibr">[17]</xref> through its NTD <xref rid="pone.0032514-Sun1" ref-type="bibr">[18]</xref>, and by binding and stimulating Akt1 within lipid rafts <xref rid="pone.0032514-Cinar1" ref-type="bibr">[19]</xref>. Many different processes are involved in the acquisition of hormone resistance <xref rid="pone.0032514-Dutt1" ref-type="bibr">[20]</xref> and they follow several diverse routes. Activation of sufficient levels of AR in a castration environment can occur through missense mutations within the AR <xref rid="pone.0032514-Brooke1" ref-type="bibr">[21]</xref>, or splice variants, which result in: enhanced binding of androgens; creation of a constitutively active receptor <xref rid="pone.0032514-Dehm2" ref-type="bibr">[22]</xref>&#x2013;<xref rid="pone.0032514-Watson1" ref-type="bibr">[25]</xref>; promiscuous binding of other ligands <xref rid="pone.0032514-Veldscholte1" ref-type="bibr">[26]</xref>&#x2013;<xref rid="pone.0032514-Duff1" ref-type="bibr">[30]</xref> or altered recruitment of co-activators and co-repressors to the NTD and LBD. The levels of AR can be raised through increased expression, altered protein turnover and gene amplification <xref rid="pone.0032514-Linja1" ref-type="bibr">[31]</xref>&#x2013;<xref rid="pone.0032514-Waltering1" ref-type="bibr">[33]</xref>. In addition, aberrant intratumoral androgen synthesis can lead to activation of AR <xref rid="pone.0032514-Knudsen1" ref-type="bibr">[34]</xref>.</p>',
        'The AR, like other members of the steroid hormone receptor family, is a ligand-activated transcription factor which has distinct structural and functional domains: the N-terminal domain (NTD) important for transactivation; the DNA binding domain (DBD) and the C-terminal ligand binding domain (LBD). Upon ligand binding, the AR undergoes conformational transformation facilitating intra- and intermolecular interactions. The transactivational capability of the AR is modulated by several signaling systems through a range of post-translational modifications. Although the AR exerts most of its actions by functioning as a transcription factor binding to specific response elements, non-genomic effects can also contribute to the regulatory outcome. Activation of the phosphatidylinositol 3-kinase (PI3K)/Akt signaling pathway not only regulates AR activity through phosphorylation of the receptor, but also has a major role in the process leading to invasion and metastasis of PCa cells through downstream phosphorylation of affiliated substrates leading to protection from apoptosis and increased cell survival. The AR can stimulate PI3K/Akt signaling by interacting directly with the p85alpha regulatory subunit of PI3K in response to synthetic and natural androgens through its NTD, and by binding and stimulating Akt1 within lipid rafts. Many different processes are involved in the acquisition of hormone resistance and they follow several diverse routes. Activation of sufficient levels of AR in a castration environment can occur through missense mutations within the AR, or splice variants, which result in: enhanced binding of androgens; creation of a constitutively active receptor; promiscuous binding of other ligands or altered recruitment of co-activators and co-repressors to the NTD and LBD. The levels of AR can be raised through increased expression, altered protein turnover and gene amplification. In addition, aberrant intratumoral androgen synthesis can lead to activation of AR.',
    ],
    [
        '<p>The predominant type of mutation i.e. loss of function, was well represented in the NTD. Mutations L57Q, E198G, D221H, A234T, S296R; S334P, P340L, P504L and D528G all displayed loss of function with E198G showing the greatest reduction (50% at 1 nM) and P340L also being present in AIS. The loss of transactivational ability was generally seen in both basal activity and across a wide range of DHT concentrations. A possible explanation for the loss of function of mutation A234T is that it is located at the start of the highly conserved motif (residues 234 to 247 <xref rid="pone.0032514-Betney1" ref-type="bibr">[56]</xref>) immediately carboxyl-terminal of TAU-1 which forms the interaction site for the Hsp70-interacting protein E3 ligase CHIP <xref rid="pone.0032514-He2" ref-type="bibr">[57]</xref>.</p>',
        'The predominant type of mutation i.e. loss of function, was well represented in the NTD. Mutations L57Q, E198G, D221H, A234T, S296R; S334P, P340L, P504L and D528G all displayed loss of function with E198G showing the greatest reduction (50% at 1 nM) and P340L also being present in AIS. The loss of transactivational ability was generally seen in both basal activity and across a wide range of DHT concentrations. A possible explanation for the loss of function of mutation A234T is that it is located at the start of the highly conserved motif (residues 234 to 247) immediately carboxyl-terminal of TAU-1 which forms the interaction site for the Hsp70-interacting protein E3 ligase CHIP.',
    ],
]


@pytest.mark.parametrize('input_text,output_text', PARSING_CASES)
@pytest.mark.parametrize('annotations', [True, False])
def test_extract_text_chunks(input_text, output_text, annotations):
    xml_input = f'<article>{input_text}</article>'
    root_nodes = [etree.fromstring(xml_input)]

    if annotations:
        map = {}
        chunks = extract_text_chunks(root_nodes, annotations_map=map)
        result, _ = strip_annotation_markers(''.join(c.text for c in chunks), map)
    else:
        chunks = extract_text_chunks(root_nodes)
        result = ''.join(c.text for c in chunks)
    print([c.text for c in chunks])
    print('extracted', ''.join(chunk.text for chunk in chunks))
    print(chunks)

    print(len(result), len(output_text))
    diff_start = -1
    for i, (c1, c2) in enumerate(zip(result, output_text)):
        if c1 != c2:
            diff_start = i
            break
    if diff_start >= 0:
        print(
            [
                repr(output_text[max(diff_start - 10, 0) : diff_start]),
                repr(output_text[diff_start : diff_start + 10]),
            ]
        )
        print(
            [
                repr(result[max(diff_start - 10, 0) : diff_start]),
                repr(result[diff_start : diff_start + 10]),
            ]
        )
    assert result == output_text


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
        (
            '(residues 234 to 247 ANN_a2b8dd34-f190-41c7-98f6-259aa8d402e8) immediately',
            {'ANN_a2b8dd34-f190-41c7-98f6-259aa8d402e8': '1'},
            '(residues 234 to 247) immediately',
            [19],
        ),
    ],
    ids=[
        'single citation',
        'multiple citations',
        'middle sentence citation',
        'round-brackets',
        'square-brackets',
        'end of brackets',
    ],
)
def test_strip_annotation_markers(text, annotations_map, expected_text, expected_locations):
    text_result, annotations_result = strip_annotation_markers(
        text, annotations_map, marker_pattern=r'ANN_[-\w]+'
    )
    assert text_result == expected_text
    locations = []
    for ann in annotations_result:
        for loc in ann.locations:
            locations.append(loc.offset)
    assert locations == expected_locations


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
        (
            'A possible (residues 234 to 247 ) immediately',
            'A possible (residues 234 to 247) immediately',
        ),
        (
            'the oncometabolite R(–)-2-hydroxyglutarate at the',
            'the oncometabolite R(-)-2-hydroxyglutarate at the',
        ),
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
