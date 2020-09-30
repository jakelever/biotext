
import xml.etree.cElementTree as etree
import bioc

def uimaxmi2bioc(xmiFilename, biocFilename):
	tree = etree.parse(xmiFilename)
	root = tree.getroot()

	metadataNode = root.find('{http:///de/tudarmstadt/ukp/dkpro/core/api/metadata/type.ecore}DocumentMetaData')
	documentTitle = metadataNode.attrib['documentTitle']

	contentNode = root.find('{http:///uima/cas.ecore}Sofa')
	content = contentNode.attrib['sofaString']

	biocDoc = bioc.BioCDocument()
	biocDoc.id = None
	biocDoc.infons['title'] = documentTitle

	passage = bioc.BioCPassage()
	passage.infons['section'] = 'article'
	passage.text = content
	passage.offset = 0
	biocDoc.add_passage(passage)
	
	yield biocDoc
