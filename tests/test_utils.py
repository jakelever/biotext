import xml.etree.cElementTree as etree
from xml.etree.ElementTree import XML

import pytest
from bioconverters.utils import (
    extract_text_chunks,
    remove_brackets_without_words,
    strip_annotation_markers,
)


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

    root_nodes = list(etree.fromstring(siblings_example))
    annotations_map = {}
    chunks = extract_text_chunks(root_nodes, annotations_map=annotations_map)
    full_text = ' '.join(c.text for c in chunks if c.text.strip())
    assert '1' in annotations_map.values()  # 113
    assert '2, 3' in annotations_map.values()  # 326
    for key in annotations_map:
        assert key in full_text
    final_text, annotations_result = strip_annotation_markers(full_text, annotations_map)
    assert final_text == expected

    locations = []
    for ann in annotations_result:
        for loc in ann.locations:
            locations.append(loc.offset)
    assert locations == [113, 325]


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
    ],
    ids=['single citation', 'multiple citations'],
)
def test_strip_annotation_markers(text, annotations_map, expected_text, expected_locations):
    text_result, annotations_result = strip_annotation_markers(text, annotations_map)
    assert text_result == expected_text
    locations = []
    for ann in annotations_result:
        for loc in ann.locations:
            locations.append(loc.offset)
    assert locations == expected_locations
