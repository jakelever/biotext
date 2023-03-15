import re
import unicodedata
import uuid
import xml.etree.cElementTree as etree
import xml.sax.saxutils as saxutils
from copy import copy
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import bioc
from unidecode import unidecode

from .constants import GREEK_ALPHABET

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
    "ext-link",  # TODO: should we keep URL content? some of these have text rather than the URL as inner content
]

# XML elements to separate text between (into different passages)
SEPARATION_LIST = [
    "title",
    "p",
    "sec",
    "def-item",
    "list-item",
    "caption",
    "thead",
    "label",
]


TABLE_DELIMITER = '\t'
TABLE_DELIMITED_TAGS = {'tr', 'th', 'td'}
# Tags that should be pre-pended with a space on merge
PSEUDO_SPACE_TAGS = {'sup', 'break'}
ANNOTATION_MARKER_PATTERN = r'ANN_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


class TextChunk:
    text: str
    xml_node: str
    xml_path: str
    is_tail: bool = False
    is_annotation: bool = False

    def __init__(
        self,
        text,
        xml_node,
        xml_path=None,
        is_tail=False,
        is_annotation=False,
    ):
        self.text = text
        self.xml_node = xml_node
        self.xml_path = xml_path
        self.is_tail = is_tail
        self.is_annotation = is_annotation

    def __str__(self) -> str:
        return self.text

    def __len__(self) -> int:
        return len(self.text)

    def __repr__(self):
        tag = self.tag
        if self.is_tail:
            tag = f'{tag}#'
        if self.text:
            tag = f'{tag}+text[{len(self.text)}]'
        if self.is_annotation:
            tag = f'{tag}@'
        return tag

    @property
    def tag(self):
        return None if self.xml_node is None else self.xml_node.tag


TagHandlerFunction = Callable[[etree.Element, Dict[str, Callable]], List[TextChunk]]


# Remove empty brackets (that could happen if the contents have been removed already
# e.g. for citation ( [] [] ) -> ( ) -> nothing
def remove_brackets_without_words(text: str) -> str:
    changed = True
    previous_text = text
    while changed:
        fixed = re.sub(r"\([^\w\t-]*\)", "", previous_text)
        fixed = re.sub(r"\[[^\w\t-]*\]", "", fixed)
        fixed = re.sub(r"\{[^\w\t-]*\}", "", fixed)
        changed = bool(previous_text != fixed)
        previous_text = fixed
    return fixed


# Some articles have titles like "[A study of ...]."
# This removes the brackets while retaining the full stop
def remove_brackets_from_titles(title_text: str) -> str:
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
    text = text.replace('°', ' ° ')
    # unidecode will default convert this to * but it is more appropriate to be converted to . as that is how it is generally used in the XML articles
    text = text.replace('·', '.')
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C" or ch == TABLE_DELIMITER)
    text = "".join(ch if unicodedata.category(ch)[0] != "Z" else " " for ch in text)

    # replace greek letters with their long-form equivalent
    for greek_letter, replacement in GREEK_ALPHABET.items():
        text = text.replace(greek_letter, replacement)

    text = unidecode(text, errors='preserve')

    # Remove repeated commands and commas next to periods
    text = re.sub(r",([^\S\t]*,)*", ",", text)
    text = re.sub(r"(,[^\S\t]*)*\.", ".", text)
    text = remove_brackets_without_words(text)

    # remove extra spaces from in-text figure/table citations
    text = re.sub(r'\([^\S\t]*([^)]*[^\s)])[^\S\t]*\)', r'(\1)', text)

    # remove trailing spaces before periods
    text = re.sub(r'[^\S\t]+\.(\s|$)', r'.\1', text)

    # remove extra spaces around commas/semi-colons
    text = re.sub(r'[^\S\t]*([,;:])([^\S\t]+)', r'\1 ', text)
    text = re.sub(r'[^\S\t]*([,;:])$', r'\1', text)

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
            prev_tail = (siblings[-1].tail or '').strip()
            if (
                not prev_tail
                or (len(prev_tail) == 1 and unicodedata.category(prev_tail[0])[0] == 'P')
            ) and elem.attrib.get('ref-type') == siblings[-1].attrib.get('ref-type'):

                siblings[-1].text = (siblings[-1].text or '') + prev_tail + (elem.text or '')
                siblings[-1].tail = elem.tail
                continue
        siblings.append(elem)
    return siblings


def drop_adjacent_sup_siblings(elem_list: List[etree.Element]) -> List[etree.Element]:
    """
    If there are 2 adjacent superscript tags, drop them and append their text to the preceding element
    """
    result = []

    for elem in elem_list:
        if elem.tag == 'sup' and len(result) > 1 and result[-1].tag == 'sup':
            # must have a non-sup element to append to the tail of
            text = [result[-1].text, result[-1].tail, elem.text, elem.tail]
            result[-2].tail += ''.join([t or '' for t in text])
            result.pop()
        else:
            result.append(elem)
    return result


def get_tag_path(mapping: Dict[etree.Element, etree.Element], node: etree.Element) -> str:
    """
    Get a string representing the path of the current XML node in the hierarchy of the XML file
    """
    path = []
    current_node = node
    while current_node is not None:
        path.append(current_node.tag)
        current_node = mapping.get(current_node)

    return '/'.join((path[::-1]))


def first_empty_index(items) -> int:
    """
    Return the index of the first falsy item in an iterable. Defaults to 0 if no items are falsy
    """
    for i, item in enumerate(items):
        if not item:
            return i
    return 0


def get_unique_child_element_index(elem: etree.Element, child_elem_type: str) -> int:
    """
    Get a child element from an XML parent node and ensure that 1 and exactly 1 element is returned

    Args:
        elem: the element to search children of
        child_elem_type: the tag type of the element in question
    """
    indices = []
    for i, child in enumerate(elem):
        if child.tag == child_elem_type:
            indices.append(i)
    if not indices:
        raise KeyError(f'unable to find child element with tag type = {child_elem_type}')
    if len(indices) > 1:
        raise ValueError(f'found multiple child elements with tag type = {child_elem_type}')
    return indices[0]


def normalize_table(elem: etree.Element) -> etree.Element:
    """
    Replace any multi-row table header with a single-row header by repeating col-spanning labels as prefixes on their sub-columns
    """
    header_elem_index = get_unique_child_element_index(elem, 'thead')
    header = elem[header_elem_index]

    header_cols = 0
    header_rows = len(header)
    for row in header:
        for header_cell in row:
            header_cols += int(header_cell.attrib.get('colspan', 1))
        break

    header_matrix = []
    filled_cells = []
    for _ in range(header_rows):
        row = []
        for _ in range(header_cols):
            row.append('')
        header_matrix.append(row)
        filled_cells.append([0 for _ in row])

    for i_row, row in enumerate(header):
        i_col = 0
        for header_cell in row:
            text = str(merge_text_chunks(chunk for chunk in tag_handler(header_cell)))
            row_cells = [r + i_row for r in range(int(header_cell.attrib.get('rowspan', 1)))]
            col_cells = [
                r + first_empty_index(filled_cells[i_row])
                for r in range(int(header_cell.attrib.get('colspan', 1)))
            ]

            for r in row_cells:
                for c in col_cells:
                    header_matrix[r][c] = text
                    filled_cells[r][c] = 1

    for col in range(header_cols):
        for row in range(1, header_rows)[::-1]:
            if header_matrix[row][col] == header_matrix[row - 1][col]:
                header_matrix[row][col] = ''

    # now flatten the header rows
    for row in header_matrix[1:]:
        for i_col, col in enumerate(row):
            if col:
                header_matrix[0][i_col] += ' ' + col

    result = [re.sub(r'[\s\n]+', ' ', col.strip()) for col in header_matrix[0]]
    new_xml = []
    for col in result:
        new_xml.append(f'<th>{saxutils.escape(col)}</th>')

    new_header_elem = etree.fromstring(f'<thead><tr>{"".join(new_xml)}</tr></thead>')
    elem[header_elem_index] = new_header_elem
    return elem


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
    if elem.tag == 'table':
        try:
            elem = normalize_table(elem)
        except KeyError:
            pass  # ignore headerless tables
    # Extract any raw text directly in XML element or just after
    head = elem.text or ""
    tail = elem.tail or ""
    # Then get the text from all child XML nodes recursively
    child_passages = []

    for child in drop_adjacent_sup_siblings(merge_adjacent_xref_siblings(elem)):
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
        if not all(
            [
                elem.tag == 'ext-link',
                head,
                re.search(r'(supp|suppl|supplementary)?\s*(table|figure)\s*s?\d+', head.lower()),
            ]
        ):
            # Check if the tag should be ignored (so don't use main contents)
            return [
                TextChunk(tail, elem, is_tail=True),
            ]

    return [TextChunk(head, elem)] + child_passages + [TextChunk(tail, elem, is_tail=True)]


def strip_annotation_markers(
    text: str, annotations_map: Dict[str, str], marker_pattern=ANNOTATION_MARKER_PATTERN
) -> Tuple[str, List[bioc.BioCAnnotation]]:
    """
    Given a set of annotations, remove any which are found in the current text and return
    the new string as well as the positions of the annotations in the transformed string

    Args:
        marker_pattern: the pattern all annotation markers are expected to match
    """
    if not annotations_map:
        return (text, [])

    transformed_annotations: List[bioc.BioCAnnotation] = []
    transformed_text = text

    pattern = (
        r'([^\S\t]*)([\(\[\{][^\S\t]*)?('
        + marker_pattern
        + r')([^\S\t]*[\)\]\}])?([^\S\t]*)([\.,;:])?'
    )

    matched_annotations: List[Tuple[int, int, str]] = []

    for match in re.finditer(pattern, text):
        ws_start, br_open, marker, br_close, ws_end, period = [match.group(i) for i in range(1, 7)]

        if marker not in annotations_map:
            continue

        start_offset = 0
        end_offset = 0

        matched_brackets = (
            br_open and br_close and br_open.strip() + br_close.strip() in {r'{}', '[]', '()'}
        )

        if not matched_brackets and (br_open or br_close):
            # do not include in the sequence to be removed from the text
            if br_open:
                start_offset += len(ws_start or '') + len(br_open or '')
                # end_offset += len(period or '') + len(ws_end or '') + len(br_close or '')
            else:
                # start_offset += len(ws_start or '') + len(br_open or '')
                end_offset += len(period or '') + len(ws_end or '') + len(br_close or '')
        elif not period:
            if ws_end:
                end_offset += len(ws_end)
            elif ws_start:
                start_offset += len(ws_start)
        else:
            # remove trailing ws and leading ws
            end_offset += len(period)

        matched_annotations.append(
            (
                match.start() + start_offset,
                match.end() - end_offset,
                marker,
            )
        )

    offset = 0
    for start, end, marker in sorted(matched_annotations):
        ann = bioc.BioCAnnotation()
        ann.id = marker
        ann.infons['citation_text'] = annotations_map[marker]
        ann.infons['type'] = 'citation'
        transformed_text = transformed_text[: start - offset] + transformed_text[end - offset :]

        # since the token place-holder is removed, must be start - 1 (and previous offset) for the new position
        annotation_offset = max(start - offset - 1, 0)  # if annotation is the first thing in a passage it may have a -1 start, should reset to 0
        ann.add_location(bioc.BioCLocation(annotation_offset, 0))

        offset += end - start
        transformed_annotations.append(ann)
    return transformed_text, transformed_annotations


def remove_style_tags(chunk_list_in: List[TextChunk], style_tags=['italic', 'bold', 'emph']):
    """
    Given some list of text chunks, simplify the list to remove consecutive style-only tags
    """
    if len(chunk_list_in) < 4:
        return chunk_list_in

    start_index = 1
    chunk_list = chunk_list_in[:]

    while start_index < len(chunk_list) - 2:
        current_tag = chunk_list[start_index]

        if current_tag.tag not in style_tags or current_tag.is_tail:
            start_index += 1
            continue

        closing_tag = chunk_list[start_index + 1]

        if closing_tag.tag != current_tag.tag or not closing_tag.is_tail:
            start_index += 1
            continue

        chunk_list[start_index - 1] = copy(chunk_list[start_index - 1])
        chunk_list[start_index - 1].text = (
            chunk_list[start_index - 1].text + current_tag.text + closing_tag.text
        )
        chunk_list = chunk_list[:start_index] + chunk_list[start_index + 2 :]

    length_diff = sum([len(c.text) for c in chunk_list_in]) - sum([len(c.text) for c in chunk_list])
    assert length_diff == 0, f'characters changed {length_diff}'
    return chunk_list


def merge_text_chunks(chunk_list: List[TextChunk], annotations_map=None) -> TextChunk:
    """
    Merge some list of text chunks and pick the most top-level xml node associated with the list to be the new node for the chunk

    Will insert temporary annotation ID markers if an annotations map is provided, otherwise will strip these out
    """
    if annotations_map is None:
        # if no mapping is expected, simply drop annotation chunks
        chunk_list = [c for c in chunk_list if not c.is_annotation]
    chunk_list = remove_style_tags(chunk_list)
    merge = []

    for i, current_chunk in enumerate(chunk_list):
        if i > 0:
            previous_chunk = chunk_list[i - 1]
            join_char = ''
            tags = {previous_chunk.tag, current_chunk.tag}
            if current_chunk.tag == 'sup':
                if not current_chunk.is_tail:
                    if re.match(r'^\s*(−|-)?\d+\s*$', current_chunk.text):
                        if (
                            previous_chunk.text
                            and unicodedata.category(previous_chunk.text[-1])[0] != 'P'
                        ):
                            join_char = '^'
                    elif (
                        current_chunk.text
                        and previous_chunk.text
                        and unicodedata.category(current_chunk.text[0])[0]
                        == unicodedata.category(previous_chunk.text[-1])[0]
                    ):
                        join_char = '-'
            elif current_chunk.tag in PSEUDO_SPACE_TAGS or (
                current_chunk.tag == 'xref' and not current_chunk.is_annotation
            ):
                join_char = ' '
            elif len(tags) == 1 and tags & TABLE_DELIMITED_TAGS and not current_chunk.is_tail:
                join_char = TABLE_DELIMITER

            merge.append(join_char)

        if current_chunk.is_annotation:
            ann_id = f'ANN_{uuid.uuid4()}'
            annotations_map[ann_id] = current_chunk.text
            merge.append(ann_id)
        else:
            merge.append(current_chunk.text)

    text = ''.join(merge)
    # Remove any newlines (as they can be trusted to be syntactically important)
    text = text.replace('\n', ' ')
    text = cleanup_text(text)

    first_non_tail_node = chunk_list[0].xml_node
    for chunk in chunk_list:
        if not chunk.is_tail and not chunk.is_annotation:
            first_non_tail_node = chunk.xml_node
            break
    return TextChunk(text, xml_node=first_non_tail_node)


def extract_text_chunks(
    element_list: Iterable[etree.Element],
    passage_tags=SEPARATION_LIST,
    tag_handlers: Dict[str, TagHandlerFunction] = {},
    annotations_map: Optional[Dict[str, str]] = None,
) -> List[TextChunk]:
    """
    Extract and beautify text from a series of XML elements

    Args:
        element_list: XML elements to be processed
        passage_tags: List of tags that should be split into their own passage. Defaults to SEPARATION_LIST.
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
