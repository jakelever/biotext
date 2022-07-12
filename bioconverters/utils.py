
import re
import unicodedata
import xml.etree.cElementTree as etree
import html

from xml.dom import minidom

# Remove empty brackets (that could happen if the contents have been removed already
# e.g. for citation ( [3] [4] ) -> ( ) -> nothing
def removeBracketsWithoutWords(text):
	fixed = re.sub(r'\([\W\s]*\)', ' ', text)
	fixed = re.sub(r'\[[\W\s]*\]', ' ', fixed)
	fixed = re.sub(r'\{[\W\s]*\}', ' ', fixed)
	return fixed

# Some older articles have titles like "[A study of ...]."
# This removes the brackets while retaining the full stop
def removeWeirdBracketsFromOldTitles(titleText):
	titleText = titleText.strip()
	if titleText[0] == '[' and titleText[-2:] == '].':
		titleText = titleText[1:-2] + '.'
	return titleText

def cleanupText(text):
	# Remove some "control-like" characters (left/right separator)
	text = text.replace(u'\u2028',' ').replace(u'\u2029',' ')
	text = "".join(ch for ch in text if unicodedata.category(ch)[0]!="C")
	text = "".join(ch if unicodedata.category(ch)[0]!="Z" else " " for ch in text)

	# Remove repeated commands and commas next to periods
	text = re.sub(',(\s*,)*',',',text)
	text = re.sub('(,\s*)*\.','.',text)

	text = re.sub(r'\[\s*<xref','[ <xref',text)
	text = re.sub(r'>\s*\]','> ]',text)

	text = re.sub(r'(\S)\[\ <xref','\\1 [ <xref',text)
	text = re.sub(r'> *\](\S)','> ] \\1',text)

	text = re.sub(r'\ +',' ',text)

	#text = re.sub('<xref','<moo',text)

	return text.strip()

# XML elements to ignore the contents of
ignoreList = ['table', 'table-wrap', 'xref', 'disp-formula', 'inline-formula', 'ref-list', 'bio', 'ack', 'graphic', 'media', 'tex-math', 'mml:math', 'object-id', 'ext-link']

# XML elements to separate text between
separationList = ['title', 'p', 'sec', 'break', 'def-item', 'list-item', 'caption', 'label', 'fig']
unicodeWhitespace = u'\t\n\x0b\x0c\r\x1c\x1d\x1e\x1f \x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000'
def extractTextFromElem(elem):
	# Extract any raw text directly in XML element or just after
	head = ""
	if elem.text:
		head = html.escape(elem.text)
	tail = ""
	if elem.tail:
		tail = html.escape(elem.tail)
	
	# Then get the text from all child XML nodes recursively
	childText = []
	for child in elem:
		childText = childText + extractTextFromElem(child)

	xmlNamespace = '{http://www.w3.org/XML/1998/namespace}'

	if elem.tag == 'xref':
		#print([head] + childText)
		headAndChild = [head] + childText
		headAndChild = [ x for x in headAndChild if x and not x == 0 ]
		headAndChildText = ' '.join(headAndChild)
		headAndChildText = headAndChildText.strip()

		if headAndChildText:
			attrib_text = [ '%s="%s"' % (k.replace(xmlNamespace,'xml'),v.replace('"','&quot;')) for k,v in elem.attrib.items() ]
			#xmlstr = '<xref ref-type="%s" rid="%s">%s</xref>' % (elem.attrib['ref-type'],elem.attrib['rid'],html.escape(elem.text))
			xmlstr = '<xref %s>%s</xref>' % (' '.join(attrib_text),headAndChildText)
			return [xmlstr] + [tail]
		else:
			return [tail]
	# Check if the tag should be ignore (so don't use main contents)
	elif elem.tag in ignoreList:
		return [tail.strip()]
	# Add a zero delimiter if it should be separated
	elif elem.tag in separationList:
		return [0] + [head] + childText + [tail]
	# Or just use the whole text
	else:
		return [head] + childText + [tail]
	

# Merge a list of extracted text blocks and deal with the zero delimiter
def extractTextFromElemList_merge(list):
	textList = []
	current = ""
	# Basically merge a list of text, except separate into a new list
	# whenever a zero appears
	for t in list:
		if t == 0: # Zero delimiter so split
			if len(current) > 0:
				textList.append(current)
				current = ""
		else: # Just keep adding
			current = current + " " + t
			current = current.strip()
	if len(current) > 0:
		textList.append(current)
	return textList
	
# Main function that extracts text from XML element or list of XML elements
def extractTextFromElemList(elemList):
	textList = []
	# Extracts text and adds delimiters (so text is accidentally merged later)
	if isinstance(elemList, list):
		for e in elemList:
			textList = textList + extractTextFromElem(e) + [0]
	else:
		textList = extractTextFromElem(elemList) + [0]

	# Merge text blocks with awareness of zero delimiters
	mergedList = extractTextFromElemList_merge(textList)
	
	# Remove any newlines (as they can be trusted to be syntactically important)
	mergedList = [ text.replace('\n', ' ') for text in mergedList ]

	# Remove no-break spaces
	mergedList = [ cleanupText(text) for text in mergedList ]

	return mergedList
	
	
def trimSentenceLengths(text):
	MAXLENGTH = 90000
	return ".".join( line[:MAXLENGTH] for line in text.split('.') )

def extractAnnotations_helper(node,currentPosition=0):
	text,annotations = '',[]
	for s in node.childNodes:
		if s.nodeType == s.ELEMENT_NODE:
			insideText,insideAnnotations = extractAnnotations_helper(s,currentPosition+len(text))

			position = (currentPosition+len(text),currentPosition+len(text)+len(insideText))

			#assert len(insideText) > 0, "Name (text inside tags) is empty for entity of type %s" % s.tagName

			if len(insideText) > 0:
				attributes = { k:v for k,v in s.attributes.items() }
				anno = { 'type':s.tagName, 'position':position, **attributes }
				annotations.append(anno)
				
			text += insideText
			annotations += insideAnnotations
		elif s.nodeType == s.TEXT_NODE:
			text += s.nodeValue
			
	return text,annotations

def extractAnnotations(text):
	docText = u"<doc>%s</doc>" % text
	#print(docText.encode('utf8'))

	xmldoc = minidom.parseString(docText.encode('utf8'))
	docNode = xmldoc.childNodes[0]

	text,annotations = extractAnnotations_helper(docNode)
	
	return text, annotations

