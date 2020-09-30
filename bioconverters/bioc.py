
import bioc

def biocxml2bioc(source):
	with open(biocFilename,'rb') as f:
		parser = bioc.BioCXMLDocumentReader(f)
		for biocDoc in parser:
			yield biocDoc

				