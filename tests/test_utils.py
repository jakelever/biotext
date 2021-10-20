import xml.etree.cElementTree as etree
from xml.etree.ElementTree import XML

import pytest
from bioconverters.utils import extract_text_chunks, remove_brackets_without_words


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
    siblings_example = """<article><abstract><p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Duis nec diam sed nisl aliquam scelerisque quis at turpis <xref>1</xref>. Vestibulum urna quam, accumsan id efficitur eget, fermentum vel eros. Pellentesque nisi urna, fringilla vitae sapien a, eleifend tempus libero. Nullam eget porta velit. Praesent bibendum dolor enim, ac lobortis<xref>2</xref>,            <xref >3</xref>.</p></abstract></article>"""
    expected = """Lorem ipsum dolor sit amet, consectetur adipiscing elit. Duis nec diam sed nisl aliquam scelerisque quis at turpis. Vestibulum urna quam, accumsan id efficitur eget, fermentum vel eros. Pellentesque nisi urna, fringilla vitae sapien a, eleifend tempus libero. Nullam eget porta velit. Praesent bibendum dolor enim, ac lobortis."""

    root_nodes = list(etree.fromstring(siblings_example))
    chunks = extract_text_chunks(root_nodes)
    full_text = ' '.join(c.text for c in chunks if c.text.strip())
    assert full_text == expected
