import re
import unicodedata


# Remove empty brackets (that could happen if the contents have been removed already
# e.g. for citation ( [3] [4] ) -> ( ) -> nothing
def remove_brackets_without_words(text):
    fixed = re.sub(r"\([\W\s]*\)", " ", text)
    fixed = re.sub(r"\[[\W\s]*\]", " ", fixed)
    fixed = re.sub(r"\{[\W\s]*\}", " ", fixed)
    return fixed


# Some older articles have titles like "[A study of ...]."
# This removes the brackets while retaining the full stop
def remove_weird_brackets_from_old_titles(title_text):
    title_text = title_text.strip()
    if title_text[0] == "[" and title_text[-2:] == "].":
        title_text = title_text[1:-2] + "."
    return title_text


def cleanup_text(text):
    # Remove some "control-like" characters (left/right separator)
    text = text.replace(u"\u2028", " ").replace(u"\u2029", " ")
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C")
    text = "".join(ch if unicodedata.category(ch)[0] != "Z" else " " for ch in text)

    # Remove repeated commands and commas next to periods
    text = re.sub(",(\s*,)*", ",", text)
    text = re.sub("(,\s*)*\.", ".", text)
    return text.strip()


# XML elements to ignore the contents of
ignore_list = [
    "table",
    "table-wrap",
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

# XML elements to separate text between
separation_list = ["title", "p", "sec", "break", "def-item", "list-item", "caption"]


def extract_text_from_elem(elem):
    # Extract any raw text directly in XML element or just after
    head = ""
    if elem.text:
        head = elem.text
    tail = ""
    if elem.tail:
        tail = elem.tail

    # Then get the text from all child XML nodes recursively
    child_text = []
    for child in elem:
        child_text = child_text + extract_text_from_elem(child)

    # Check if the tag should be ignore (so don't use main contents)
    if elem.tag in ignore_list:
        return [tail.strip()]
    # Add a zero delimiter if it should be separated
    elif elem.tag in separation_list:
        return [0] + [head] + child_text + [tail]
    # Or just use the whole text
    else:
        return [head] + child_text + [tail]


# Merge a list of extracted text blocks and deal with the zero delimiter
def extract_text_from_elem_list_merge(list):
    text_list = []
    current = ""
    # Basically merge a list of text, except separate into a new list
    # whenever a zero appears
    for t in list:
        if t == 0:  # Zero delimiter so split
            if len(current) > 0:
                text_list.append(current)
                current = ""
        else:  # Just keep adding
            current = current + " " + t
            current = current.strip()
    if len(current) > 0:
        text_list.append(current)
    return text_list


# Main function that extracts text from XML element or list of XML elements
def extract_text_from_elem_list(elem_list):
    text_list = []
    # Extracts text and adds delimiters (so text is accidentally merged later)
    if isinstance(elem_list, list):
        for e in elem_list:
            text_list = text_list + extract_text_from_elem(e) + [0]
    else:
        text_list = extract_text_from_elem(elem_list) + [0]

    # Merge text blocks with awareness of zero delimiters
    merged_list = extract_text_from_elem_list_merge(text_list)

    # Remove any newlines (as they can be trusted to be syntactically important)
    merged_list = [text.replace("\n", " ") for text in merged_list]

    # Remove no-break spaces
    merged_list = [cleanup_text(text) for text in merged_list]

    return merged_list


def trim_sentence_lengths(text):
    MAXLENGTH = 90000
    return ".".join(line[:MAXLENGTH] for line in text.split("."))
