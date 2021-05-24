from typing import Iterable, TextIO, Union

import bioc

from .bioc import biocxml2bioc
from .pmcxml import pmcxml2bioc
from .pubmedxml import pubmedxml2bioc


def docs2bioc(source: Union[str, TextIO], format: str) -> Iterable[bioc.BioCDocument]:
    """
    Args:
        source: filehandler or path to the input file
    """
    if format == "biocxml":
        return biocxml2bioc(source)
    elif format == "pubmedxml":
        return pubmedxml2bioc(source)
    elif format == "pmcxml":
        return pmcxml2bioc(source)
    else:
        raise RuntimeError("Unknown format: %s" % format)


accepted_in_formats = ["biocxml", "pubmedxml", "pmcxml"]
accepted_out_formats = ["biocxml", "txt"]


def convert(in_files, in_format, out_file, out_format):
    out_bioc_handle, out_txt_handle = None, None

    assert (
        in_format in accepted_in_formats
    ), "%s is not an accepted input format. Options are: %s" % (
        in_format,
        "/".join(accepted_in_formats),
    )
    assert (
        out_format in accepted_out_formats
    ), "%s is not an accepted output format. Options are: %s" % (
        out_format,
        "/".join(accepted_out_formats),
    )

    if out_format == "biocxml":
        out_bioc_handle = bioc.BioCXMLDocumentWriter(out_file)
    elif out_format == "txt":
        out_txt_handle = open(out_file, "w", encoding="utf-8")

    for in_file in in_files:

        for bioc_doc in docs2bioc(in_file, in_format):

            if out_format == "biocxml":
                out_bioc_handle.write_document(bioc_doc)
            elif out_format == "txt":
                for passage in bioc_doc.passages:
                    out_txt_handle.write(passage.text)
                    out_txt_handle.write("\n\n")

    if out_format == "biocxml":
        out_bioc_handle.close()
    elif out_format == "txt":
        out_txt_handle.close()
