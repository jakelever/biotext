
import xml.etree.cElementTree as etree
import calendar
import bioc
import re
import html

from .utils import extractTextFromElemList
from .utils import removeWeirdBracketsFromOldTitles
from .utils import removeBracketsWithoutWords
from .utils import trimSentenceLengths

from .utils import extractAnnotations

def getJournalDateForMedlineFile(elem,pmid):
	yearRegex = re.compile(r'(18|19|20)\d\d')

	monthMapping = {}
	for i,m in enumerate(calendar.month_name):
		monthMapping[m] = i
	for i,m in enumerate(calendar.month_abbr):
		monthMapping[m] = i

	# Try to extract the publication date
	pubDateField = elem.find('./MedlineCitation/Article/Journal/JournalIssue/PubDate')
	medlineDateField = elem.find('./MedlineCitation/Article/Journal/JournalIssue/PubDate/MedlineDate')

	assert not pubDateField is None, "Couldn't find PubDate field for PMID=%s" % pmid

	medlineDateField = pubDateField.find('./MedlineDate')
	pubDateField_Year = pubDateField.find('./Year')
	pubDateField_Month = pubDateField.find('./Month')
	pubDateField_Day = pubDateField.find('./Day')

	pubYear,pubMonth,pubDay = None,None,None
	if not medlineDateField is None:
		regexSearch = re.search(yearRegex,medlineDateField.text)
		if regexSearch:
			pubYear = regexSearch.group()
		monthSearch = [ c for c in (list(calendar.month_name) + list(calendar.month_abbr)) if c != '' and c in medlineDateField.text ]
		if len(monthSearch) > 0:
			pubMonth = monthSearch[0]
	else:
		if not pubDateField_Year is None:
			pubYear = pubDateField_Year.text
		if not pubDateField_Month is None:
			pubMonth = pubDateField_Month.text
		if not pubDateField_Day is None:
			pubDay = pubDateField_Day.text

	if not pubYear is None:
		pubYear = int(pubYear)
		if not (pubYear > 1700 and pubYear < 2100):
			pubYear = None

	if not pubMonth is None:
		if pubMonth in monthMapping:
			pubMonth = monthMapping[pubMonth]
		pubMonth = int(pubMonth)
	if not pubDay is None:
		pubDay = int(pubDay)

	return pubYear,pubMonth,pubDay

def getPubmedEntryDate(elem,pmid):
	pubDateFields = elem.findall('./PubmedData/History/PubMedPubDate')
	allDates = {}
	for pubDateField in pubDateFields:
		assert 'PubStatus' in pubDateField.attrib
		#if 'PubStatus' in pubDateField.attrib and pubDateField.attrib['PubStatus'] == "pubmed":
		pubDateField_Year = pubDateField.find('./Year')
		pubDateField_Month = pubDateField.find('./Month')
		pubDateField_Day = pubDateField.find('./Day')
		pubYear = int(pubDateField_Year.text)
		pubMonth = int(pubDateField_Month.text)
		pubDay = int(pubDateField_Day.text)

		dateType = pubDateField.attrib['PubStatus']
		if pubYear > 1700 and pubYear < 2100:
			allDates[dateType] = (pubYear,pubMonth,pubDay)

	if len(allDates) == 0:
		return None,None,None

	if 'pubmed' in allDates:
		pubYear,pubMonth,pubDay = allDates['pubmed']
	elif 'entrez' in allDates:
		pubYear,pubMonth,pubDay = allDates['entrez']
	elif 'medline' in allDates:
		pubYear,pubMonth,pubDay = allDates['medline']
	else:
		pubYear,pubMonth,pubDay = list(allDates.values())[0]

	return pubYear,pubMonth,pubDay

pubTypeSkips = {"Research Support, N.I.H., Intramural","Research Support, Non-U.S. Gov't","Research Support, U.S. Gov't, P.H.S.","Research Support, N.I.H., Extramural","Research Support, U.S. Gov't, Non-P.H.S.","English Abstract"}
doiRegex = re.compile(r'^[0-9\.]+\/.+[^\/]$')
def processMedlineFile(source):
	for event, elem in etree.iterparse(source, events=('start', 'end', 'start-ns', 'end-ns')):
		if (event=='end' and elem.tag=='PubmedArticle'): #MedlineCitation'):
			# Try to extract the pmidID
			pmidField = elem.find('./MedlineCitation/PMID')
			assert not pmidField is None
			pmid = pmidField.text

			journalYear,journalMonth,journalDay = getJournalDateForMedlineFile(elem,pmid)
			entryYear,entryMonth,entryDay = getPubmedEntryDate(elem,pmid)

			jComparison = tuple ( 9999 if d is None else d for d in [ journalYear,journalMonth,journalDay ] )
			eComparison = tuple ( 9999 if d is None else d for d in [ entryYear,entryMonth,entryDay ] )
			if jComparison < eComparison: # The PubMed entry has been delayed for some reason so let's try the journal data
				pubYear,pubMonth,pubDay = journalYear,journalMonth,journalDay
			else:
				pubYear,pubMonth,pubDay = entryYear,entryMonth,entryDay

			# Extract the authors
			authorElems = elem.findall('./MedlineCitation/Article/AuthorList/Author')
			authors = []
			for authorElem in authorElems:
				forename = authorElem.find('./ForeName')
				lastname = authorElem.find('./LastName')
				collectivename = authorElem.find('./CollectiveName')

				name = None
				if forename is not None and lastname is not None and forename.text is not None and lastname.text is not None:
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
			chemicalElems = elem.findall('./MedlineCitation/ChemicalList/Chemical/NameOfSubstance')
			for chemicalElem in chemicalElems:
				chemID = chemicalElem.attrib['UI']
				name = chemicalElem.text
				#chemicals.append((chemID,name))
				chemicals.append("%s|%s" % (chemID,name))
			chemicalsTxt = "\t".join(chemicals)

			meshHeadings = []
			meshElems = elem.findall('./MedlineCitation/MeshHeadingList/MeshHeading')
			for meshElem in meshElems:
				descriptorElem = meshElem.find('./DescriptorName')
				meshID = descriptorElem.attrib['UI']
				majorTopicYN = descriptorElem.attrib['MajorTopicYN']
				name = descriptorElem.text

				assert not '|' in meshID and not '~' in meshID, "Found delimiter in %s" % meshID
				assert not '|' in majorTopicYN and not '~' in majorTopicYN, "Found delimiter in %s" % majorTopicYN
				assert not '|' in name and not '~' in name, "Found delimiter in %s" % name

				meshHeading = "Descriptor|%s|%s|%s" % (meshID,majorTopicYN,name)

				qualifierElems = meshElem.findall('./QualifierName')
				for qualifierElem in qualifierElems:
					meshID = qualifierElem.attrib['UI']
					majorTopicYN = qualifierElem.attrib['MajorTopicYN']
					name = qualifierElem.text

					assert not '|' in meshID and not '~' in meshID, "Found delimiter in %s" % meshID
					assert not '|' in majorTopicYN and not '~' in majorTopicYN, "Found delimiter in %s" % majorTopicYN
					assert not '|' in name and not '~' in name, "Found delimiter in %s" % name

					meshHeading += "~Qualifier|%s|%s|%s" % (meshID,majorTopicYN,name)

				meshHeadings.append(meshHeading)
			meshHeadingsTxt = "\t".join(meshHeadings)

			supplementaryConcepts = []
			conceptElems = elem.findall('./MedlineCitation/SupplMeshList/SupplMeshName')
			for conceptElem in conceptElems:
				conceptID = conceptElem.attrib['UI']
				conceptType = conceptElem.attrib['Type']
				conceptName = conceptElem.text
				#supplementaryConcepts.append((conceptID,conceptType,conceptName))
				supplementaryConcepts.append("%s|%s|%s" % (conceptID,conceptType,conceptName))
			supplementaryConceptsTxt = "\t".join(supplementaryConcepts)

			doiElems = elem.findall("./PubmedData/ArticleIdList/ArticleId[@IdType='doi']")
			dois = [ doiElem.text for doiElem in doiElems if doiElem.text and doiRegex.match(doiElem.text) ]

			doi = None
			if dois:
				doi = dois[0] # We'll just use DOI the first one provided

			pmcElems = elem.findall("./PubmedData/ArticleIdList/ArticleId[@IdType='pmc']")
			assert len(pmcElems) <= 1, "Foud more than one PMCID with PMID: %s" % pmid
			pmcid = None
			if len(pmcElems) == 1:
				pmcid = pmcElems[0].text

			pubTypeElems = elem.findall('./MedlineCitation/Article/PublicationTypeList/PublicationType')
			pubType = [ e.text for e in pubTypeElems if not e.text in pubTypeSkips ]
			pubTypeTxt = "|".join(pubType)
					
			# Extract the title of paper
			title = elem.findall('./MedlineCitation/Article/ArticleTitle')
			titleText = extractTextFromElemList(title)
			titleText = [ removeWeirdBracketsFromOldTitles(t) for t in titleText ]
			titleText = [ t for t in titleText if len(t) > 0 ]
			#titleText = [ html.unescape(t) for t in titleText ]
			titleText = [ removeBracketsWithoutWords(t) for t in titleText ]
			
			# Extract the abstract from the paper
			abstract = elem.findall('./MedlineCitation/Article/Abstract/AbstractText')
			abstractText = extractTextFromElemList(abstract)
			abstractText = [ t for t in abstractText if len(t) > 0 ]
			#abstractText = [ html.unescape(t) for t in abstractText ]
			abstractText = [ removeBracketsWithoutWords(t) for t in abstractText ]
			
			journalTitleFields = elem.findall('./MedlineCitation/Article/Journal/Title')
			journalTitleISOFields = elem.findall('./MedlineCitation/Article/Journal/ISOAbbreviation')
			journalTitle = " ".join(extractTextFromElemList(journalTitleFields))
			journalISOTitle = " ".join(extractTextFromElemList(journalTitleISOFields))

			document = {}
			document["pmid"] = pmid
			document["pmcid"] = pmcid
			document["doi"] = doi
			document["pubYear"] = pubYear
			document["pubMonth"] = pubMonth
			document["pubDay"] = pubDay
			document["title"] = titleText
			document["abstract"] = abstractText
			document["journal"] = journalTitle
			document["journalISO"] = journalISOTitle
			document["authors"] = authors
			document["chemicals"] = chemicalsTxt
			document["meshHeadings"] = meshHeadingsTxt
			document["supplementaryMesh"] = supplementaryConceptsTxt
			document["publicationTypes"] = pubTypeTxt

			yield document
		

			# Important: clear the current element from memory to keep memory usage low
			elem.clear()
		

def pubmedxml2bioc(source):
	for pmDoc in processMedlineFile(source):
		biocDoc = bioc.BioCDocument()
		biocDoc.id = pmDoc["pmid"]
		biocDoc.infons['title'] = " ".join(pmDoc["title"])
		biocDoc.infons['pmid'] = pmDoc["pmid"]
		biocDoc.infons['pmcid'] = pmDoc["pmcid"]
		biocDoc.infons['doi'] = pmDoc["doi"]
		biocDoc.infons['year'] = pmDoc["pubYear"]
		biocDoc.infons['month'] = pmDoc["pubMonth"]
		biocDoc.infons['day'] = pmDoc["pubDay"]
		biocDoc.infons['journal'] = pmDoc["journal"]
		biocDoc.infons['journalISO'] = pmDoc["journalISO"]
		biocDoc.infons['authors'] = ", ".join(pmDoc["authors"])
		biocDoc.infons['chemicals'] = pmDoc['chemicals']
		biocDoc.infons['meshHeadings'] = pmDoc['meshHeadings']
		biocDoc.infons['supplementaryMesh'] = pmDoc['supplementaryMesh']
		biocDoc.infons['publicationTypes'] = pmDoc['publicationTypes']

		offset = 0
		for section in ["title","abstract"]:
			for textSource in pmDoc[section]:
				textSource = trimSentenceLengths(textSource)
				textSource, annotations = extractAnnotations(textSource)

				passage = bioc.BioCPassage()
				passage.infons['section'] = section
				passage.text = textSource
				passage.offset = offset
				offset += len(textSource)
				biocDoc.add_passage(passage)

		yield biocDoc
