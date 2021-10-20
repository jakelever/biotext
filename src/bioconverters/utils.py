import re
import unicodedata
import xml.etree.cElementTree as etree
from typing import Callable, Dict, Iterable, List

# XML elements to ignore the contents of
IGNORE_LIST = [
    "xref",
    "disp-formula",
    "inline-formula",
    "ref-list",
    "bio",
    "ack",
    "graphic",
    "media",
    "tex-math",
    "mml:math",
    "object-id",
    "ext-link",
]

# XML elements to separate text between (into different passages)
SEPERATION_LIST = ["title", "p", "sec", "break", "def-item", "list-item", "caption", "table"]


class TextChunk:
    text: str
    xml_node: str
    xml_path: str

    def __init__(self, text, xml_node, xml_path=None):
        self.text = text
        self.xml_node = xml_node
        self.xml_path = xml_path

    def __str__(self) -> str:
        return self.text


TagHandlerFunction = Callable[[etree.Element, Dict[str, Callable]], List[TextChunk]]


# Remove empty brackets (that could happen if the contents have been removed already
# e.g. for citation ( [3] [4] ) -> ( ) -> nothing
def remove_brackets_without_words(text: str) -> str:
    fixed = re.sub(r"\([\W\s]*\)", " ", text)
    fixed = re.sub(r"\[[\W\s]*\]", " ", fixed)
    fixed = re.sub(r"\{[\W\s]*\}", " ", fixed)
    return fixed


# Some older articles have titles like "[A study of ...]."
# This removes the brackets while retaining the full stop
def remove_weird_brackets_from_old_titles(title_text: str) -> str:
    title_text = title_text.strip()
    if title_text[0] == "[" and title_text[-2:] == "].":
        title_text = title_text[1:-2] + "."
    return title_text


def cleanup_text(text: str) -> str:
    # Remove some "control-like" characters (left/right separator)
    text = text.replace(u"\u2028", " ").replace(u"\u2029", " ")
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C")
    text = "".join(ch if unicodedata.category(ch)[0] != "Z" else " " for ch in text)

    # Remove repeated commands and commas next to periods
    text = re.sub(r",(\s*,)*", ",", text)
    text = re.sub(r"(,\s*)*\.", ".", text)
    return text.strip()


def trim_sentence_lengths(text: str) -> str:
    MAXLENGTH = 90000
    return ".".join(line[:MAXLENGTH] for line in text.split("."))


def build_xml_parent_mapping(
    root_nodes: Iterable[etree.Element],
) -> Dict[etree.Element, etree.Element]:
    """
    Build a map of each XML node element to its respective parent
    """
    mapping = {}
    queue = root_nodes
    while queue:
        current_node = queue.pop(0)
        for child in current_node:
            queue.append(child)
            mapping[child] = current_node
    return mapping


def get_tag_path(mapping: Dict[etree.Element, etree.Element], node: etree.Element) -> str:
    """
    Get a string representing the path of the currentl XML node in the heirachry of the XML file
    """
    path = []
    current_node = node
    while current_node is not None:
        path.append(current_node.tag)
        current_node = mapping.get(current_node)

    return '/'.join((path[::-1]))


def tag_handler(
    elem: etree.Element, custom_handlers: Dict[str, TagHandlerFunction] = {}
) -> List[TextChunk]:
    """
    Parses an XML node element into a series of text chunks

    Args:
        elem: the element to be parsed
        custom_handlers: overloads the default behaviour for a given tag type. Defaults to {}.
    """
    # custom handlers override the default behaviour for any tag
    if elem.tag in custom_handlers:
        try:
            return custom_handlers[elem.tag](elem, custom_handlers=custom_handlers)
        except NotImplementedError:
            pass
    # Extract any raw text directly in XML element or just after
    head = (elem.text or "").strip()
    tail = (elem.tail or "").strip()

    # Then get the text from all child XML nodes recursively
    child_passages = []
    child_tags = []
    for child in elem:
        child_passages.extend(tag_handler(child, custom_handlers=custom_handlers))
        child_tags.append(child.tag)

    if elem.tag == 'sup' and len(child_tags) > 1 and set(child_tags) == {'xref'}:
        # this is an in-text citation
        return [TextChunk(head, elem), TextChunk(tail, elem)]
    elif elem.tag == 'xref' and 'xref' in IGNORE_LIST:
        # keep xref tags that refer to internal elements like tables and figures
        if not re.search(r'\b(Figure|Fig|Table)s?(\.|\b)', head, re.IGNORECASE):
            if 'supp' in head.lower() or 'fig' in head.lower():  # TODO: remove warning
                print('IGNORING XREF', elem.tag, head)
            return [TextChunk(tail, elem)]
    elif elem.tag in IGNORE_LIST:
        # Check if the tag should be ignored (so don't use main contents)
        return [TextChunk(tail, elem)]

    return [TextChunk(head, elem)] + child_passages + [TextChunk(tail, elem)]


def extract_text_chunks(
    element_list: Iterable[etree.Element],
    passage_tags=SEPERATION_LIST,
    tag_handlers: Dict[str, TagHandlerFunction] = {},
) -> List[TextChunk]:
    """
    Extract and beautify text from a series of XML elements

    Args:
        element_list: XML elements to be processed
        passage_tags: List of tags that should be split into their own passage. Defaults to SEPERATION_LIST.
        tag_handlers: Custom overloads for processing various XML tags. Defaults to {}.

    Returns:
        List of text chunks grouped into passages
    """
    if not isinstance(element_list, list):
        element_list = [element_list]
    raw_text_chunks = []
    for elem in element_list:
        raw_text_chunks.extend(tag_handler(elem, tag_handlers))
    merged_text_chunks = [[]]

    for chunk in raw_text_chunks:
        if chunk.xml_node and chunk.xml_node.tag in passage_tags:
            # start a new tag set
            merged_text_chunks.append([chunk])
        else:
            merged_text_chunks[-1].append(chunk)

    def merge_text_chunks(passage_list):
        text = ' '.join([p.text.strip() for p in passage_list])
        # Remove any newlines (as they can be trusted to be syntactically important)
        text = text.replace('\n', '')
        # Remove no-break spaces
        text = cleanup_text(text)
        return TextChunk(text, passage_list[0].xml_node)

    merged_chunks = [merge_text_chunks(m) for m in merged_text_chunks if m]

    # assign the XML path to each passage
    mapping = build_xml_parent_mapping(element_list)
    for chunk in merged_chunks:
        chunk.xml_path = get_tag_path(mapping, chunk.xml_node)

    return merged_chunks
