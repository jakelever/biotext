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
    "def-item",
    "list-item",
    "caption",
    "thead",
    "label",
]

TABLE_DELIMITER = '\t'
TABLE_DELIMATED_TAGS = {'tr', 'th', 'td'}


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

    def __repr__(self):
        tag = self.tag
        if self.is_tail:
            tag = f'{tag}#'
        ns = '-ns' if self.non_separating else ''
        tag = f'{tag}{ns}'
        if self.text:
            tag = f'{tag}+text[{len(self.text)}]'
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
        fixed = re.sub(r"\([^\w\t]*\)", "", previous_text)
        fixed = re.sub(r"\[[^\w\t]*\]", "", fixed)
        fixed = re.sub(r"\{[^\w\t]*\}", "", fixed)
        changed = bool(previous_text != fixed)
        previous_text = fixed
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
            prev_tail = (siblings[-1].tail or '').strip()
            if (
                siblings[-1].tail
                and len(prev_tail) == 1
                and unicodedata.category(prev_tail)[0] == 'P'
                and elem.attrib.get('ref-type') == siblings[-1].attrib.get('ref-type')
            ):

                siblings[-1].text = (siblings[-1].text or '') + prev_tail + (elem.text or '')
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
        if not all(
            [
                elem.tag == 'ext-link',
                head,
                re.search(r'(supp|suppl|supplementary)?\s*(table|figure)\s*s?\d+', head.lower()),
            ]
        ):
            # Check if the tag should be ignored (so don't use main contents)
            return [
                TextChunk(tail, elem, non_separating=True, is_tail=True),
            ]

    return [TextChunk(head, elem)] + child_passages + [TextChunk(tail, elem, is_tail=True)]


def strip_annotation_markers(
    text: str,
    annotations_map: Dict[str, str],
    marker_pattern=r'ANN_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
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
        r'([^\S\t]*)([\(\[\{][^\S\t]*)?(' + marker_pattern + r')([^\S\t]*[\)\]\}])?([^\S\t]*)(\.)?'
    )

    matched_annotations: List[Tuple[int, int, str]] = []

    for match in re.finditer(pattern, text):
        ws_start, br_open, marker, br_close, ws_end, period = [match.group(i) for i in range(1, 7)]

        if marker not in annotations_map:
            continue

        start_offset = 0
        end_offset = 0

        matched_brackets = (
            br_open and br_close and br_open.strip() + br_close.strip() in {'\{\}', '[]', '()'}
        )

        if not matched_brackets and (br_open or br_close):
            # do not include in the sequence to be removed from the text
            start_offset += len(ws_start or '') + len(br_open or '')
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
        ann.add_location(bioc.BioCLocation(start - offset - 1, 0))

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
            elif len(tags) == 1 and tags & TABLE_DELIMATED_TAGS and not current_chunk.is_tail:
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


def count_nones(l):
    return sum(1 if x is None else 0 for x in l)


def non_none_max(l):
    values = [v for v in l if v is not None]
    if values:
        return max(values)
    return None


def mark_acronyms(text, max_intra_word_letters=1) -> Dict[str, str]:
    """
    Regex-based method to detect obvious acronym definitions
    """
    words = re.split(r'(\s+|,|;|\.|\(|\)|{|})', text.strip())

    # replace with ext package if end up using more than just here
    stop_words = {'and', 'or', 'it', 'the', 'of', 'in', 'with', 'to'}
    acronyms = {}

    for acronym_pos in range(1, len(words) - 1):
        acronym = words[acronym_pos]
        if all(
            [
                words[acronym_pos - 1] == '(',
                words[acronym_pos + 1] == ')',
                re.match(r'^[A-Z][a-zA-Z]*[A-Z]$', acronym),
            ]
        ):
            # simplest case, number of tokens
            letter_index_matches = [set() for _ in acronym]

            for words_pos in range(acronym_pos - 2, -1, -1):
                if words[words_pos] == '.':  # assume end of sentence
                    break

                for letter_pos, letter in enumerate(acronym):
                    if words[words_pos] and words[words_pos][0].lower() == letter.lower():
                        letter_index_matches[letter_pos].add(words_pos)

            if not letter_index_matches[0]:
                continue

            paths = [[c] for c in letter_index_matches[0]]

            for choices in letter_index_matches[1:]:
                new_paths = []
                for path in paths:
                    curr_max = non_none_max(path)
                    for choice in choices | {None}:
                        if curr_max is None or choice is None or choice >= curr_max:
                            new_paths.append(path[:] + [choice])
                paths = new_paths

            paths = [p for p in paths if count_nones(p) <= max_intra_word_letters]
            best_path = min(paths, key=count_nones)

            for i, (match, letter) in enumerate(zip(best_path, acronym)):
                if match is not None:
                    continue
                prev_choice = None
                if i > 0 and letter.lower():
                    prev_choice = best_path[i - 1]
                next_choice = None
                if i < len(best_path) - 1:
                    next_choice = best_path[i + 1]

                prev_choice = prev_choice or next_choice
                next_choice = next_choice or prev_choice

                if prev_choice is None or next_choice is None:
                    break

                for word_pos in range(prev_choice, next_choice + 1):
                    if (
                        letter.lower() in words[word_pos]
                        and words[word_pos].lower() not in stop_words
                    ):
                        best_path[i] = word_pos

            if count_nones(best_path) == 0:
                defn = ''.join(words[min(best_path) : max(best_path) + 1])
                acronyms[acronym] = defn

    return acronyms
