import bioc


def biocxml2bioc(source):
    with open(bioc_filename, "rb") as f:
        parser = bioc.BioCXMLDocumentReader(f)
        for bioc_doc in parser:
            yield bioc_doc
