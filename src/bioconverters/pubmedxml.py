import calendar
import html
import re
import xml.etree.cElementTree as etree
from typing import Callable, Dict, Iterable, Optional, TextIO, Tuple, Union

try:
    # python 3.8+
    from typing import TypedDict  # type: ignore
except ImportError:
    from typing_extensions import TypedDict

import bioc

from .utils import (
    TagHandlerFunction,
    extract_text_chunks,
    remove_brackets_without_words,
    remove_weird_brackets_from_old_titles,
    trim_sentence_lengths,
)

DateTuple = Tuple[Optional[int], Optional[int], Optional[int]]


class MedlineArticle(TypedDict):
    pmid: str
    pmcid: str
    doi: str
    pubYear: Optional[int]
    pubMonth: Optional[int]
    pubDay: Optional[int]
    title: Iterable[str]
    abstract: str
    journal: str
    journalISO: str
    authors: Iterable[str]
    chemicals: str
    meshHeadings: str
    supplementaryMesh: str
    publicationTypes: str


def get_journal_date_for_medline_file(elem: etree.Element, pmid: Union[str, int]) -> DateTuple:
    """
    Scrapes the Journal Date from the Medline XML element tree.

    Args:
        elem: XML element to be scraped/parsed
        pmid: Pubmed ID of the article, only used for reporting errors
    """
    year_regex = re.compile(r"(18|19|20)\d\d")

    month_mapping = {}
    for i, m in enumerate(calendar.month_name):
        month_mapping[m] = i
    for i, m in enumerate(calendar.month_abbr):
        month_mapping[m] = i

    # Try to extract the publication date
    pub_date_field = elem.find("./MedlineCitation/Article/Journal/JournalIssue/PubDate")
    medline_date_field = elem.find(
        "./MedlineCitation/Article/Journal/JournalIssue/PubDate/MedlineDate"
    )

    assert pub_date_field is not None, "Couldn't find PubDate field for PMID=%s" % pmid

    medline_date_field = pub_date_field.find("./MedlineDate")
    pub_date_field_year = pub_date_field.find("./Year")
    pub_date_field_month = pub_date_field.find("./Month")
    pub_date_field_day = pub_date_field.find("./Day")

    pub_year, pub_month, pub_day = None, None, None
    if medline_date_field is not None:
        regex_search = re.search(year_regex, medline_date_field.text)
        if regex_search:
            pub_year = regex_search.group()
        month_search = [
            c
            for c in (list(calendar.month_name) + list(calendar.month_abbr))
            if c != "" and c in medline_date_field.text
        ]
        if len(month_search) > 0:
            pub_month = month_search[0]
    else:
        if pub_date_field_year is not None:
            pub_year = pub_date_field_year.text
        if pub_date_field_month is not None:
            pub_month = pub_date_field_month.text
        if pub_date_field_day is not None:
            pub_day = pub_date_field_day.text

    if pub_year is not None:
        pub_year = int(pub_year)
        if not (pub_year > 1700 and pub_year < 2100):
            pub_year = None

    if pub_month is not None:
        if pub_month in month_mapping:
            pub_month = month_mapping[pub_month]  # type: ignore
        pub_month = int(pub_month)
    if pub_day is not None:
        pub_day = int(pub_day)

    return pub_year, pub_month, pub_day


def get_pubmed_entry_date(elem: etree.Element, pmid) -> DateTuple:
    """
    Args:
        pmid: not used?
    """
    pub_date_fields = elem.findall("./PubmedData/History/PubMedPubDate")
    all_dates = {}
    for pub_date_field in pub_date_fields:
        assert "PubStatus" in pub_date_field.attrib
        # if 'PubStatus' in pub_date_field.attrib and pub_date_field.attrib['PubStatus'] == "pubmed":
        pub_date_field_year = pub_date_field.find("./Year")
        pub_date_field_month = pub_date_field.find("./Month")
        pub_date_field_day = pub_date_field.find("./Day")
        pub_year = int(pub_date_field_year.text)
        pub_month = int(pub_date_field_month.text)
        pub_day = int(pub_date_field_day.text)

        date_type = pub_date_field.attrib["PubStatus"]
        if pub_year > 1700 and pub_year < 2100:
            all_dates[date_type] = (pub_year, pub_month, pub_day)

    if len(all_dates) == 0:
        return None, None, None

    if "pubmed" in all_dates:
        pub_year, pub_month, pub_day = all_dates["pubmed"]
    elif "entrez" in all_dates:
        pub_year, pub_month, pub_day = all_dates["entrez"]
    elif "medline" in all_dates:
        pub_year, pub_month, pub_day = all_dates["medline"]
    else:
        pub_year, pub_month, pub_day = list(all_dates.values())[0]

    return pub_year, pub_month, pub_day


pub_type_skips = {
    "Research Support, N.I.H., Intramural",
    "Research Support, Non-U.S. Gov't",
    "Research Support, U.S. Gov't, P.H.S.",
    "Research Support, N.I.H., Extramural",
    "Research Support, U.S. Gov't, Non-P.H.S.",
    "English Abstract",
}
doi_regex = re.compile(r"^[0-9\.]+\/.+[^\/]$")


def process_medline_file(
    source: Union[str, TextIO], tag_handlers: Dict[str, TagHandlerFunction] = {}
) -> Iterable[MedlineArticle]:
    """
    Args:
        source: path to the MEDLINE xml file
    """
    for event, elem in etree.iterparse(source, events=("start", "end", "start-ns", "end-ns")):
        if event == "end" and elem.tag == "PubmedArticle":  # MedlineCitation'):
            # Try to extract the pmid_id
            pmid_field = elem.find("./MedlineCitation/PMID")
            assert pmid_field is not None
            pmid = pmid_field.text

            journal_year, journal_month, journal_day = get_journal_date_for_medline_file(elem, pmid)
            entry_year, entry_month, entry_day = get_pubmed_entry_date(elem, pmid)

            jComparison = tuple(
                9999 if d is None else d for d in [journal_year, journal_month, journal_day]
            )
            eComparison = tuple(
                9999 if d is None else d for d in [entry_year, entry_month, entry_day]
            )
            if (
                jComparison < eComparison
            ):  # The PubMed entry has been delayed for some reason so let's try the journal data
                pub_year, pub_month, pub_day = journal_year, journal_month, journal_day
            else:
                pub_year, pub_month, pub_day = entry_year, entry_month, entry_day

            # Extract the authors
            author_elems = elem.findall("./MedlineCitation/Article/AuthorList/Author")
            authors = []
            for author_elem in author_elems:
                forename = author_elem.find("./ForeName")
                lastname = author_elem.find("./LastName")
                collectivename = author_elem.find("./CollectiveName")

                name = None
                if (
                    forename is not None
                    and lastname is not None
                    and forename.text is not None
                    and lastname.text is not None
                ):
                    name = "%s %s" % (forename.text, lastname.text)
                elif lastname is not None and lastname.text is not None:
                    name = lastname.text
                elif forename is not None and forename.text is not None:
                    name = forename.text
                elif collectivename is not None and collectivename.text is not None:
                    name = collectivename.text
                else:
                    raise RuntimeError("Unable to find authors in Pubmed citation (PMID=%s)" % pmid)
                authors.append(name)

            chemicals = []
            chemical_elems = elem.findall("./MedlineCitation/ChemicalList/Chemical/NameOfSubstance")
            for chemical_elem in chemical_elems:
                chem_id = chemical_elem.attrib["UI"]
                name = chemical_elem.text
                # chemicals.append((chem_id,name))
                chemicals.append("%s|%s" % (chem_id, name))
            chemicals_txt = "\t".join(chemicals)

            mesh_headings = []
            mesh_elems = elem.findall("./MedlineCitation/MeshHeadingList/MeshHeading")
            for mesh_elem in mesh_elems:
                descriptor_elem = mesh_elem.find("./DescriptorName")
                mesh_id = descriptor_elem.attrib["UI"]
                major_topic_yn = descriptor_elem.attrib["MajorTopicYN"]
                name = descriptor_elem.text

                assert "|" not in mesh_id and "~" not in mesh_id, "Found delimiter in %s" % mesh_id
                assert "|" not in major_topic_yn and "~" not in major_topic_yn, (
                    "Found delimiter in %s" % major_topic_yn
                )
                assert "|" not in name and "~" not in name, "Found delimiter in %s" % name

                mesh_heading = "Descriptor|%s|%s|%s" % (mesh_id, major_topic_yn, name)

                qualifier_elems = mesh_elem.findall("./QualifierName")
                for qualifier_elem in qualifier_elems:
                    mesh_id = qualifier_elem.attrib["UI"]
                    major_topic_yn = qualifier_elem.attrib["MajorTopicYN"]
                    name = qualifier_elem.text

                    assert "|" not in mesh_id and "~" not in mesh_id, (
                        "Found delimiter in %s" % mesh_id
                    )
                    assert "|" not in major_topic_yn and "~" not in major_topic_yn, (
                        "Found delimiter in %s" % major_topic_yn
                    )
                    assert "|" not in name and "~" not in name, "Found delimiter in %s" % name

                    mesh_heading += "~Qualifier|%s|%s|%s" % (mesh_id, major_topic_yn, name)

                mesh_headings.append(mesh_heading)
            mesh_headings_txt = "\t".join(mesh_headings)

            supplementary_concepts = []
            concept_elems = elem.findall("./MedlineCitation/SupplMeshList/SupplMeshName")
            for concept_elem in concept_elems:
                concept_id = concept_elem.attrib["UI"]
                concept_type = concept_elem.attrib["Type"]
                concept_name = concept_elem.text
                # supplementary_concepts.append((concept_id,concept_type,concept_name))
                supplementary_concepts.append("%s|%s|%s" % (concept_id, concept_type, concept_name))
            supplementary_concepts_txt = "\t".join(supplementary_concepts)

            doi_elems = elem.findall("./PubmedData/ArticleIdList/ArticleId[@IdType='doi']")
            dois = [
                doi_elem.text
                for doi_elem in doi_elems
                if doi_elem.text and doi_regex.match(doi_elem.text)
            ]

            doi = None
            if dois:
                doi = dois[0]  # We'll just use DOI the first one provided

            pmc_elems = elem.findall("./PubmedData/ArticleIdList/ArticleId[@IdType='pmc']")
            assert len(pmc_elems) <= 1, "Foud more than one PMCID with PMID: %s" % pmid
            pmcid = None
            if len(pmc_elems) == 1:
                pmcid = pmc_elems[0].text

            pub_type_elems = elem.findall(
                "./MedlineCitation/Article/PublicationTypeList/PublicationType"
            )
            pub_type = [e.text for e in pub_type_elems if e.text not in pub_type_skips]
            pub_type_txt = "|".join(pub_type)

            # Extract the title of paper
            title = elem.findall("./MedlineCitation/Article/ArticleTitle")
            title_text = extract_text_chunks(title, tag_handlers=tag_handlers)
            title_text = [
                remove_weird_brackets_from_old_titles(chunk.text)
                for chunk in title_text
                if chunk.text
            ]
            title_text = [t for t in title_text if len(t) > 0]
            title_text = [html.unescape(t) for t in title_text]
            title_text = [remove_brackets_without_words(t) for t in title_text]

            # Extract the abstract from the paper
            abstract = elem.findall("./MedlineCitation/Article/Abstract/AbstractText")
            abstract_text = extract_text_chunks(abstract, tag_handlers=tag_handlers)
            abstract_text = [chunk.text for chunk in abstract_text if len(chunk.text) > 0]
            abstract_text = [html.unescape(t) for t in abstract_text]
            abstract_text = [remove_brackets_without_words(t) for t in abstract_text]

            journal_title_fields = elem.findall("./MedlineCitation/Article/Journal/Title")
            journal_title_iso_fields = elem.findall(
                "./MedlineCitation/Article/Journal/ISOAbbreviation"
            )

            journal_title, journal_iso_title = "", ""
            assert len(journal_title_fields) <= 1, "Error with pmid=%s" % pmid
            assert len(journal_title_iso_fields) <= 1, "Error with pmid=%s" % pmid
            if journal_title_fields:
                journal_title = journal_title_fields[0].text
            if journal_title_iso_fields:
                journal_iso_title = journal_title_iso_fields[0].text

            document = {}
            document["pmid"] = pmid
            document["pmcid"] = pmcid
            document["doi"] = doi
            document["pubYear"] = pub_year
            document["pubMonth"] = pub_month
            document["pubDay"] = pub_day
            document["title"] = title_text
            document["abstract"] = abstract_text
            document["journal"] = journal_title
            document["journalISO"] = journal_iso_title
            document["authors"] = authors
            document["chemicals"] = chemicals_txt
            document["meshHeadings"] = mesh_headings_txt
            document["supplementaryMesh"] = supplementary_concepts_txt
            document["publicationTypes"] = pub_type_txt

            yield MedlineArticle(document)

            # Important: clear the current element from memory to keep memory usage low
            elem.clear()


def pubmedxml2bioc(
    source: Union[str, TextIO],
    tag_handlers: Dict[str, TagHandlerFunction] = {},
    trim_sentences=True,
) -> Iterable[bioc.BioCDocument]:
    """
    Args:
        source: path to the MEDLINE xml file
    """
    for pm_doc in process_medline_file(source, tag_handlers=tag_handlers):
        bioc_doc = bioc.BioCDocument()
        bioc_doc.id = pm_doc["pmid"]
        bioc_doc.infons["title"] = " ".join(pm_doc["title"])
        bioc_doc.infons["pmid"] = pm_doc["pmid"]
        bioc_doc.infons["pmcid"] = pm_doc["pmcid"]
        bioc_doc.infons["doi"] = pm_doc["doi"]
        bioc_doc.infons["year"] = pm_doc["pubYear"]
        bioc_doc.infons["month"] = pm_doc["pubMonth"]
        bioc_doc.infons["day"] = pm_doc["pubDay"]
        bioc_doc.infons["journal"] = pm_doc["journal"]
        bioc_doc.infons["journalISO"] = pm_doc["journalISO"]
        bioc_doc.infons["authors"] = ", ".join(pm_doc["authors"])
        bioc_doc.infons["chemicals"] = pm_doc["chemicals"]
        bioc_doc.infons["meshHeadings"] = pm_doc["meshHeadings"]
        bioc_doc.infons["supplementaryMesh"] = pm_doc["supplementaryMesh"]
        bioc_doc.infons["publicationTypes"] = pm_doc["publicationTypes"]

        offset = 0
        for section in ["title", "abstract"]:
            for text_source in pm_doc[section]:
                if trim_sentences:
                    text_source = trim_sentence_lengths(text_source)
                passage = bioc.BioCPassage()
                passage.infons["section"] = section
                passage.text = text_source
                passage.offset = offset
                offset += len(text_source)
                bioc_doc.add_passage(passage)

        yield bioc_doc
