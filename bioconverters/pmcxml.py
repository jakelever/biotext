import calendar
import html
import xml.etree.cElementTree as etree
from typing import Iterable, Optional, Tuple

try:
    # python 3.8+
    from typing import TypedDict  # type: ignore
except ImportError:
    from typing_extensions import TypedDict

import bioc

from .utils import (
    extract_text_from_elem_list,
    remove_brackets_without_words,
    remove_weird_brackets_from_old_titles,
    trim_sentence_lengths,
)


class TextSource(TypedDict):
    title: Iterable[str]
    subtitle: Iterable[str]
    abstract: Iterable[str]
    article: Iterable[str]
    back: Iterable[str]
    floating: Iterable[str]


class PmcArticle(TypedDict):
    pmid: str
    pmcid: str
    doi: str
    pubYear: str
    pubMonth: str
    pubDay: str
    journal: str
    journalISO: str
    textSources: TextSource


def get_meta_info_for_pmc_article(
    article_elem,
) -> Tuple[str, str, str, Optional[str], Optional[int], Optional[str], str, str]:
    month_mapping = {}
    for i, m in enumerate(calendar.month_name):
        month_mapping[m] = i
    for i, m in enumerate(calendar.month_abbr):
        month_mapping[m] = i

    # Attempt to extract the PubMed ID, PubMed Central IDs and DOIs
    pmid_text = ""
    pmcid_text = ""
    doi_text = ""
    article_id = article_elem.findall("./front/article-meta/article-id") + article_elem.findall(
        "./front-stub/article-id"
    )
    for a in article_id:
        if a.text and "pub-id-type" in a.attrib and a.attrib["pub-id-type"] == "pmid":
            pmid_text = a.text.strip().replace("\n", " ")
        if a.text and "pub-id-type" in a.attrib and a.attrib["pub-id-type"] == "pmc":
            pmcid_text = a.text.strip().replace("\n", " ")
        if a.text and "pub-id-type" in a.attrib and a.attrib["pub-id-type"] == "doi":
            doi_text = a.text.strip().replace("\n", " ")

    # Attempt to get the publication date
    pubdates = article_elem.findall("./front/article-meta/pub-date") + article_elem.findall(
        "./front-stub/pub-date"
    )
    pub_year, pub_month, pub_day = None, None, None
    if len(pubdates) >= 1:
        most_complete, completeness = None, 0
        for pubdate in pubdates:
            pub_year_field = pubdate.find("./year")
            if pub_year_field is not None:
                pub_year = pub_year_field.text.strip().replace("\n", " ")
            pub_season_field = pubdate.find("./season")
            if pub_season_field is not None:
                pub_season = pub_season_field.text.strip().replace("\n", " ")
                month_search = [
                    c
                    for c in (list(calendar.month_name) + list(calendar.month_abbr))
                    if c != "" and c in pub_season
                ]
                if len(month_search) > 0:
                    pub_month = month_mapping[month_search[0]]
            pub_month_field = pubdate.find("./month")
            if pub_month_field is not None:
                pub_month = pub_month_field.text.strip().replace("\n", " ")
            pub_day_field = pubdate.find("./day")
            if pub_day_field is not None:
                pub_day = pub_day_field.text.strip().replace("\n", " ")

            this_completeness = sum(x is not None for x in [pub_year, pub_month, pub_day])
            if this_completeness > completeness:
                most_complete = pub_year, pub_month, pub_day
        pub_year, pub_month, pub_day = most_complete

    journal = (
        article_elem.findall("./front/journal-meta/journal-title")
        + article_elem.findall("./front/journal-meta/journal-title-group/journal-title")
        + article_elem.findall("./front-stub/journal-title-group/journal-title")
    )
    assert len(journal) <= 1
    journal_text = " ".join(extract_text_from_elem_list(journal))

    journal_iso_text = ""
    journal_iso = article_elem.findall("./front/journal-meta/journal-id") + article_elem.findall(
        "./front-stub/journal-id"
    )
    for field in journal_iso:
        if "journal-id-type" in field.attrib and field.attrib["journal-id-type"] == "iso-abbrev":
            journal_iso_text = field.text

    return (
        pmid_text,
        pmcid_text,
        doi_text,
        pub_year,
        pub_month,
        pub_day,
        journal_text,
        journal_iso_text,
    )


def process_pmc_file(source: str) -> Iterable[PmcArticle]:
    # Skip to the article element in the file
    for event, elem in etree.iterparse(source, events=("start", "end", "start-ns", "end-ns")):
        if event == "end" and elem.tag == "article":
            (
                pmid_text,
                pmcid_text,
                doi_text,
                pub_year,
                pub_month,
                pub_day,
                journal,
                journal_iso,
            ) = get_meta_info_for_pmc_article(elem)

            # We're going to process the main article along with any subarticles
            # And if any of the subarticles have distinguishing IDs (e.g. PMID), then
            # that'll be used, otherwise the parent article IDs will be used
            subarticles = [elem] + elem.findall("./sub-article")

            for article_elem in subarticles:
                if article_elem == elem:
                    # This is the main parent article. Just use its IDs
                    (
                        sub_pmid_text,
                        sub_pmcid_text,
                        sub_doi_text,
                        sub_pub_year,
                        sub_pub_month,
                        sub_pub_day,
                        sub_journal,
                        sub_journal_iso,
                    ) = (
                        pmid_text,
                        pmcid_text,
                        doi_text,
                        pub_year,
                        pub_month,
                        pub_day,
                        journal,
                        journal_iso,
                    )
                else:
                    # Check if this subarticle has any distinguishing IDs and use them instead
                    (
                        sub_pmid_text,
                        sub_pmcid_text,
                        sub_doi_text,
                        sub_pub_year,
                        sub_pub_month,
                        sub_pub_day,
                        sub_journal,
                        sub_journal_iso,
                    ) = get_meta_info_for_pmc_article(article_elem)
                    if sub_pmid_text == "" and sub_pmcid_text == "" and sub_doi_text == "":
                        sub_pmid_text, sub_pmcid_text, sub_doi_text = (
                            pmid_text,
                            pmcid_text,
                            doi_text,
                        )
                    if sub_pub_year is None:
                        sub_pub_year = pub_year
                        sub_pub_month = pub_month
                        sub_pub_day = pub_day
                    if sub_journal is None:
                        sub_journal = journal
                        sub_journal_iso = journal_iso

                # Extract the title of paper
                title = article_elem.findall(
                    "./front/article-meta/title-group/article-title"
                ) + article_elem.findall("./front-stub/title-group/article-title")
                assert len(title) <= 1
                title_text = extract_text_from_elem_list(title)
                title_text = [remove_weird_brackets_from_old_titles(t) for t in title_text]

                # Get the subtitle (if it's there)
                subtitle = article_elem.findall(
                    "./front/article-meta/title-group/subtitle"
                ) + article_elem.findall("./front-stub/title-group/subtitle")
                subtitle_text = extract_text_from_elem_list(subtitle)
                subtitle_text = [remove_weird_brackets_from_old_titles(t) for t in subtitle_text]

                # Extract the abstract from the paper
                abstract = article_elem.findall(
                    "./front/article-meta/abstract"
                ) + article_elem.findall("./front-stub/abstract")
                abstract_text = extract_text_from_elem_list(abstract)

                # Extract the full text from the paper as well as supplementaries and floating blocks of text
                article_text = extract_text_from_elem_list(article_elem.findall("./body"))
                back_text = extract_text_from_elem_list(article_elem.findall("./back"))
                floating_text = extract_text_from_elem_list(article_elem.findall("./floats-group"))

                document = PmcArticle(
                    {
                        "pmid": sub_pmid_text,
                        "pmcid": sub_pmcid_text,
                        "doi": sub_doi_text,
                        "pubYear": sub_pub_year,
                        "pubMonth": sub_pub_month,
                        "pubDay": sub_pub_day,
                        "journal": sub_journal,
                        "journalISO": sub_journal_iso,
                    }
                )

                text_sources = TextSource({})
                text_sources["title"] = title_text
                text_sources["subtitle"] = subtitle_text
                text_sources["abstract"] = abstract_text
                text_sources["article"] = article_text
                text_sources["back"] = back_text
                text_sources["floating"] = floating_text

                for k in text_sources.keys():
                    tmp = text_sources[k]
                    tmp = [t for t in tmp if len(t) > 0]
                    tmp = [html.unescape(t) for t in tmp]
                    tmp = [remove_brackets_without_words(t) for t in tmp]
                    text_sources[k] = tmp

                document["textSources"] = text_sources
                yield document

            # Less important here (compared to abstracts) as each article file is not too big
            elem.clear()


allowed_subsections = {
    "abbreviations",
    "additional information",
    "analysis",
    "author contributions",
    "authors' contributions",
    "authors’ contributions",
    "background",
    "case report",
    "competing interests",
    "conclusion",
    "conclusions",
    "conflict of interest",
    "conflicts of interest",
    "consent",
    "data analysis",
    "data collection",
    "discussion",
    "ethics statement",
    "funding",
    "introduction",
    "limitations",
    "material and methods",
    "materials",
    "materials and methods",
    "measures",
    "method",
    "methods",
    "participants",
    "patients and methods",
    "pre-publication history",
    "related literature",
    "results",
    "results and discussion",
    "statistical analyses",
    "statistical analysis",
    "statistical methods",
    "statistics",
    "study design",
    "summary",
    "supplementary data",
    "supplementary information",
    "supplementary material",
    "supporting information",
}


def pmcxml2bioc(source: str) -> Iterable[bioc.BioCDocument]:
    try:
        for pmc_doc in process_pmc_file(source):
            bioc_doc = bioc.BioCDocument()
            bioc_doc.id = pmc_doc["pmid"]
            bioc_doc.infons["title"] = " ".join(pmc_doc["textSources"]["title"])
            bioc_doc.infons["pmid"] = pmc_doc["pmid"]
            bioc_doc.infons["pmcid"] = pmc_doc["pmcid"]
            bioc_doc.infons["doi"] = pmc_doc["doi"]
            bioc_doc.infons["year"] = pmc_doc["pubYear"]
            bioc_doc.infons["month"] = pmc_doc["pubMonth"]
            bioc_doc.infons["day"] = pmc_doc["pubDay"]
            bioc_doc.infons["journal"] = pmc_doc["journal"]
            bioc_doc.infons["journalISO"] = pmc_doc["journalISO"]

            offset = 0
            for group_name, text_source_group in pmc_doc["textSources"].items():
                subsection = None
                for text_source in text_source_group:
                    text_source = trim_sentence_lengths(text_source)
                    passage = bioc.BioCPassage()

                    subsection_check = text_source.lower().strip("01234567890. ")
                    if subsection_check in allowed_subsections:
                        subsection = subsection_check

                    passage.infons["section"] = group_name
                    passage.infons["subsection"] = subsection
                    passage.text = text_source
                    passage.offset = offset
                    offset += len(text_source)
                    bioc_doc.add_passage(passage)

            yield bioc_doc

    except etree.ParseError:
        raise RuntimeError("Parsing error in PMC xml file: %s" % source)
