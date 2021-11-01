import re
import unicodedata
import uuid
import xml.etree.cElementTree as etree
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import bioc

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
SEPERATION_LIST = [
    "title",
    "p",
    "sec",
    "break",
    "def-item",
    "list-item",
    "caption",
    "thead",
    "label",
]

TABLE_DELIMITER = '\t'


class TextChunk:
    text: str
    xml_node: str
    xml_path: str
    non_separating: bool = False
    is_tail: bool = False
    is_annotation: bool = False

    def __init__(
        self,
        text,
        xml_node,
        xml_path=None,
        non_separating=False,
        is_tail=False,
        is_annotation=False,
    ):
        self.text = text
        self.xml_node = xml_node
        self.xml_path = xml_path
        self.non_separating = non_separating or is_annotation
        self.is_tail = is_tail
        self.is_annotation = is_annotation

    def __str__(self) -> str:
        return self.text

    def __len__(self) -> int:
        return len(self.text)

    @property
    def tag(self):
        return None if self.xml_node is None else self.xml_node.tag


TagHandlerFunction = Callable[[etree.Element, Dict[str, Callable]], List[TextChunk]]


# Remove empty brackets (that could happen if the contents have been removed already
# e.g. for citation ( [3] [4] ) -> ( ) -> nothing
def remove_brackets_without_words(text: str) -> str:
    fixed = re.sub(r"\((\W|[^\S\t])*\)", "", text)
    fixed = re.sub(r"\[(\W|[^\S\t])*\]", "", fixed)
    fixed = re.sub(r"\{(\W|[^\S\t])*\}", "", fixed)
    return fixed


# Some older articles have titles like "[A study of ...]."
# This removes the brackets while retaining the full stop
def remove_weird_brackets_from_old_titles(title_text: str) -> str:
    title_text = title_text.strip()
    if title_text[0] == "[" and title_text[-2:] == "].":
        title_text = title_text[1:-2] + "."
    return title_text


def cleanup_text(text: str) -> str:
    """
    Clean up non-tab extra whitespace, remove control characters and extra leftover brackets etc
    """
    # Remove some "control-like" characters (left/right separator)
    text = text.replace(u"\u2028", " ").replace(u"\u2029", " ")
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch == TABLE_DELIMITER)
    text = "".join(ch if unicodedata.category(ch)[0] != "Z" else " " for ch in text)

    # Remove repeated commands and commas next to periods
    text = re.sub(r",([^\S\t]*,)*", ",", text)
    text = re.sub(r"(,[^\S\t]*)*\.", ".", text)
    text = remove_brackets_without_words(text)

    # remove extra spaces from in-text figute/table citations
    text = re.sub(r'\([^\S\t]*([^)]*[^\s)])[^\S\t]*\)', r'(\1)', text)

    # remove trailing spaces before periods
    text = re.sub(r'[^\S\t]+\.(\s|$)', r'.\1', text)

    # remove extra spaces around commas/semi-colons
    text = re.sub(r'[^\S\t]*([,;])[^\S\t]+', r'\1 ', text)

    # trim leading and trailing non tab whitespace
    text = re.sub(r'(^|\t)([^\S\t]+)', r'\1', text)
    text = re.sub(r'([^\S\t]+)(\t|$)', r'\2', text)

    # trim multiple non-tab spaces
    text = re.sub(r'[^\S\t][^\S\t]+', ' ', text)

    return text


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


def merge_adjacent_xref_siblings(elem_list):
    """
    If two XML elements in a list are adjacent and both xrefs separated only by punctuation, merge them
    """
    siblings = []

    for elem in elem_list:
        if siblings and elem.tag == 'xref' and siblings[-1].tag == 'xref':
            # merge these 2 if the tail of the first element is a punctuation mark
            prev_tail = siblings[-1].tail.strip()
            if (
                siblings[-1].tail
                and len(prev_tail) == 1
                and unicodedata.category(prev_tail)[0] == 'P'
                and elem.attrib.get('ref-type') == siblings[-1].attrib.get('ref-type')
            ):
                siblings[-1].text = siblings[-1].text + siblings[-1].tail + elem.text
                siblings[-1].tail = elem.tail
                continue
        siblings.append(elem)
    return siblings


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

    for child in merge_adjacent_xref_siblings(elem):
        child_passages.extend(tag_handler(child, custom_handlers=custom_handlers))

    if elem.tag == 'xref' and 'xref' in IGNORE_LIST:
        # keep xref tags that refer to internal elements like tables and figures
        if elem.attrib.get('ref-type', '') == 'bibr':
            if tail:
                return [
                    TextChunk(head, elem, is_annotation=True),
                    TextChunk(tail, elem, is_tail=True),
                ]
            else:
                return [TextChunk(head, elem, is_annotation=True)]
    elif elem.tag in IGNORE_LIST:
        # Check if the tag should be ignored (so don't use main contents)
        return [
            TextChunk(tail, elem, non_separating=True, is_tail=True),
        ]

    return [TextChunk(head, elem)] + child_passages + [TextChunk(tail, elem, is_tail=True)]


def strip_annotation_markers(
    text: str, annotations_map: Dict[str, str]
) -> Tuple[str, List[bioc.BioCAnnotation]]:
    """
    Given a set of annotations, remove any which are found in the current text and return
    the new string as well as the positions of the annotations in the transformed string
    """
    matched_annotations: List[Tuple[int, int.str]] = []
    for ann_marker in annotations_map:
        # citation in brackets
        patterns = [
            (r'[^\S\t]?\(' + re.escape(ann_marker) + r'\)', 0),  # citation in brackets
            (
                r'[^\S\t]' + re.escape(ann_marker) + r'\.',
                1,
            ),  # citation at end of sentence, remove extra whitespace
            (
                r'[^\S\t]' + re.escape(ann_marker) + r'[^\S\t]',
                1,
            ),  # citation surrounded by whitespace
            (re.escape(ann_marker), 0),  # citation by itself
        ]
        for pattern, end_offset in patterns:
            match = re.search(pattern, text)
            if match:
                matched_annotations.append((match.start(), match.end() - end_offset, ann_marker))
                break

    transformed_annotations: List[bioc.BioCAnnotation] = []
    transformed_text = text
    offset = 0

    def find_last_token_pos(string):
        match = re.search(r'(\S+)\s*$', string)
        return match.start(1), match.end(1)

    for start, end, marker in matched_annotations:
        ann = bioc.BioCAnnotation()
        ann.id = marker
        ann.infons['citation_text'] = annotations_map[marker]
        ann.infons['type'] = 'citation'
        token_start, token_end = find_last_token_pos(transformed_text[: start - offset])
        transformed_text = transformed_text[: start - offset] + transformed_text[end - offset :]

        ann.text = transformed_text[token_start:token_end]
        ann.add_location(bioc.BioCLocation(token_start, len(ann.text)))

        offset += end - start
        transformed_annotations.append(ann)
    return transformed_text, transformed_annotations


def merge_text_chunks(chunk_list, annotations_map=None) -> TextChunk:
    """
    Merge some list of text chunks and pick the most top-level xml node associated with the list to be the new node for the chunk

    Will insert temporary annotation ID markers if an annotations map is provided, otherwise will strip these out
    """
    if annotations_map is None:
        # if no mapping is expected, simply drop annotation chunks
        chunk_list = [c for c in chunk_list if not c.is_annotation]

    merge = []

    for i, current_chunk in enumerate(chunk_list):
        if i > 0:
            previous_chunk = chunk_list[i - 1]
            join_char = ' '
            tags = {previous_chunk.tag, current_chunk.tag}
            if any(
                [
                    previous_chunk.is_annotation,
                    current_chunk.is_annotation,
                    previous_chunk.non_separating,
                    current_chunk.non_separating,
                    current_chunk.is_tail and not (current_chunk.text or previous_chunk.text),
                ]
            ):
                join_char = ''
            elif (tags == {'td'} or tags == {'tr'}) and not current_chunk.is_tail:
                join_char = TABLE_DELIMITER

            merge.append(join_char)

        current_text = cleanup_text(current_chunk.text)
        if current_chunk.is_annotation:
            ann_id = f'ANN_{uuid.uuid4()}'
            annotations_map[ann_id] = current_text
            merge.append(ann_id)
        else:
            merge.append(current_text)

    text = ''.join(merge)
    # Remove any newlines (as they can be trusted to be syntactically important)
    text = text.replace('\n', '')
    text = cleanup_text(text)

    first_non_tail_node = chunk_list[0].xml_node
    for chunk in chunk_list:
        if not chunk.is_tail and not chunk.is_annotation:
            first_non_tail_node = chunk.xml_node
            break
    return TextChunk(text, xml_node=first_non_tail_node)


def extract_text_chunks(
    element_list: Iterable[etree.Element],
    passage_tags=SEPERATION_LIST,
    tag_handlers: Dict[str, TagHandlerFunction] = {},
    annotations_map: Optional[Dict[str, str]] = None,
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
    chunks_to_be_merged = [[]]

    for chunk in raw_text_chunks:
        if chunk.xml_node is not None and chunk.tag in passage_tags:
            # start a new tag set
            chunks_to_be_merged.append([chunk])
        else:
            chunks_to_be_merged[-1].append(chunk)

    merged_chunks = [merge_text_chunks(m, annotations_map) for m in chunks_to_be_merged if m]

    # assign the XML path to each passage
    mapping = build_xml_parent_mapping(element_list)
    for chunk in merged_chunks:
        chunk.xml_path = get_tag_path(mapping, chunk.xml_node)

    return [c for c in merged_chunks if c.text]
