
import pymarc
import bioc

from .utils import trimSentenceLengths

def writeMarcXMLRecordToBiocFile(record):
	metadata = record['008'].value()
	language = metadata[35:38]
	if language != 'eng':
		return

	recordid = record['001'].value()

	title = record.title()
	textSources = [title]

	abstract = None
	if '520' in record and 'a' in record['520']:
		abstract = record['520']['a']
		textSources.append(abstract)

	#print recordid, language, title, abstract
	biocDoc = bioc.BioCDocument()
	biocDoc.id = recordid

	offset = 0
	for textSource in textSources:
		if isinstance(textSource,six.string_types):
			textSource = trimSentenceLengths(textSource)
			passage = bioc.BioCPassage()
			passage.text = textSource
			passage.offset = offset
			offset += len(textSource)
			biocDoc.add_passage(passage)

	yield biocDoc
	
	
def marcxml2bioc(source,biocFilename):

	return pymarc.map_xml(writeMarcXMLRecordToBiocFile,source)
	