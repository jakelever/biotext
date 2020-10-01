
import argparse
import bioc

from .pubmedxml import pubmedxml2bioc
from .pmcxml import pmcxml2bioc
from .bioc import biocxml2bioc

def docs2bioc(source,format):
	if format == 'biocxml':
		return biocxml2bioc(source)
	elif format == 'pubmedxml':
		return pubmedxml2bioc(source)
	elif format == 'pmcxml':
		return pmcxml2bioc(source)
	else:
		raise RuntimeError("Unknown format: %s" % format)

acceptedInFormats = ['biocxml','pubmedxml','pmcxml']
acceptedOutFormats = ['biocxml','txt']
def convert(inFiles,inFormat,outFile,outFormat):
	outBiocHandle,outTxtHandle = None,None
	
	assert inFormat in acceptedInFormats, "%s is not an accepted input format. Options are: %s" % (inFormat, "/".join(acceptedInFormats))
	assert outFormat in acceptedOutFormats, "%s is not an accepted output format. Options are: %s" % (outFormat, "/".join(acceptedOutFormats))

	if outFormat == 'biocxml':
		outBiocHandle = bioc.BioCXMLDocumentWriter(outFile)
	elif outFormat == 'txt':
		outTxtHandle = open(outFile,'w','utf-8')

	for inFile in inFiles:

		for biocDoc in docs2bioc(inFile,inFormat):
			
			if outFormat == 'biocxml':
				outBiocHandle.write_document(biocDoc)
			elif outFormat == 'txt':
				for passage in biocDoc.passages:
					outTxtHandle.write(passage.text)
					outTxtHandle.write("\n\n")
				
	if outFormat == 'biocxml':
		outBiocHandle.close()
	elif outFormat == 'txt':
		outTxtHandle.close()
				
