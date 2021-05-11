
import xml.etree.cElementTree as etree
import bioc
import calendar
import html
import sys

from .utils import extractTextFromElemList
from .utils import removeWeirdBracketsFromOldTitles
from .utils import removeBracketsWithoutWords
from .utils import trimSentenceLengths

from .utils import extractAnnotations

def getMetaInfoForPMCArticle(articleElem):
	monthMapping = {}
	for i,m in enumerate(calendar.month_name):
		monthMapping[m] = i
	for i,m in enumerate(calendar.month_abbr):
		monthMapping[m] = i

	# Attempt to extract the PubMed ID, PubMed Central IDs and DOIs
	pmidText = ''
	pmcidText = ''
	doiText = ''
	article_id = articleElem.findall('./front/article-meta/article-id') + articleElem.findall('./front-stub/article-id')
	for a in article_id:
		if a.text and 'pub-id-type' in a.attrib and a.attrib['pub-id-type'] == 'pmid':
			pmidText = a.text.strip().replace('\n',' ')
		if a.text and 'pub-id-type' in a.attrib and a.attrib['pub-id-type'] == 'pmc':
			pmcidText = a.text.strip().replace('\n',' ')
		if a.text and 'pub-id-type' in a.attrib and a.attrib['pub-id-type'] == 'doi':
			doiText = a.text.strip().replace('\n',' ')
			
	# Attempt to get the publication date
	pubdates = articleElem.findall('./front/article-meta/pub-date') + articleElem.findall('./front-stub/pub-date')
	pubYear,pubMonth,pubDay = None,None,None
	if len(pubdates) >= 1:
		mostComplete,completeness = None,0
		for pubdate in pubdates:
			pubYear_Field = pubdate.find("./year")
			if not pubYear_Field is None:
				pubYear = pubYear_Field.text.strip().replace('\n',' ')
			pubSeason_Field = pubdate.find("./season")
			if not pubSeason_Field is None:
				pubSeason = pubSeason_Field.text.strip().replace('\n',' ')
				monthSearch = [ c for c in (list(calendar.month_name) + list(calendar.month_abbr)) if c != '' and c in pubSeason ]
				if len(monthSearch) > 0:
					pubMonth = monthMapping[monthSearch[0]]
			pubMonth_Field = pubdate.find("./month")
			if not pubMonth_Field is None:
				pubMonth = pubMonth_Field.text.strip().replace('\n',' ')
			pubDay_Field = pubdate.find("./day")
			if not pubDay_Field is None:
				pubDay = pubDay_Field.text.strip().replace('\n',' ')

			thisCompleteness = sum(not x is None for x in [pubYear,pubMonth,pubDay])
			if thisCompleteness > completeness:
				mostComplete = pubYear,pubMonth,pubDay
		pubYear,pubMonth,pubDay = mostComplete
					
	journal = articleElem.findall('./front/journal-meta/journal-title') + articleElem.findall('./front/journal-meta/journal-title-group/journal-title') + articleElem.findall('./front-stub/journal-title-group/journal-title')
	assert len(journal) <= 1
	journalText = " ".join(extractTextFromElemList(journal))
	
	journalISOText = ''
	journalISO = articleElem.findall('./front/journal-meta/journal-id') + articleElem.findall('./front-stub/journal-id')
	for field in journalISO:
		if 'journal-id-type' in field.attrib and field.attrib['journal-id-type'] == "iso-abbrev":
			journalISOText = field.text

	return pmidText,pmcidText,doiText,pubYear,pubMonth,pubDay,journalText,journalISOText


def processPMCFile(source):
	# Skip to the article element in the file
	for event, elem in etree.iterparse(source, events=('start', 'end', 'start-ns', 'end-ns')):
		if (event=='end' and elem.tag=='article'):
			pmidText,pmcidText,doiText,pubYear,pubMonth,pubDay,journal,journalISO = getMetaInfoForPMCArticle(elem)

			# We're going to process the main article along with any subarticles
			# And if any of the subarticles have distinguishing IDs (e.g. PMID), then
			# that'll be used, otherwise the parent article IDs will be used
			subarticles = [elem] + elem.findall('./sub-article')
			
			for articleElem in subarticles:
				if articleElem == elem:
					# This is the main parent article. Just use its IDs
					subPmidText,subPmcidText,subDoiText,subPubYear,subPubMonth,subPubDay,subJournal,subJournalISO = pmidText,pmcidText,doiText,pubYear,pubMonth,pubDay,journal,journalISO
				else:
					# Check if this subarticle has any distinguishing IDs and use them instead
					subPmidText,subPmcidText,subDoiText,subPubYear,subPubMonth,subPubDay,subJournal,subJournalISO = getMetaInfoForPMCArticle(articleElem)
					if subPmidText=='' and subPmcidText == '' and subDoiText == '':
						subPmidText,subPmcidText,subDoiText = pmidText,pmcidText,doiText
					if subPubYear == None:
						subPubYear = pubYear
						subPubMonth = pubMonth
						subPubDay = pubDay
					if subJournal == None:
						subJournal = journal
						subJournalISO = journalISO

				#print('pmcid:', subPmcidText)
						
				# Extract the title of paper
				title = articleElem.findall('./front/article-meta/title-group/article-title') + articleElem.findall('./front-stub/title-group/article-title')
				assert len(title) <= 1
				titleText = extractTextFromElemList(title)
				titleText = [ removeWeirdBracketsFromOldTitles(t) for t in titleText ]
				
				# Get the subtitle (if it's there)
				subtitle = articleElem.findall('./front/article-meta/title-group/subtitle') + articleElem.findall('./front-stub/title-group/subtitle')
				subtitleText = extractTextFromElemList(subtitle)
				subtitleText = [ removeWeirdBracketsFromOldTitles(t) for t in subtitleText ]
				
				# Extract the abstract from the paper
				abstract = articleElem.findall('./front/article-meta/abstract') + articleElem.findall('./front-stub/abstract')
				abstractText = extractTextFromElemList(abstract)

				
				# Extract the full text from the paper as well as supplementaries and floating blocks of text
				articleText = extractTextFromElemList(articleElem.findall('./body'))
				backText = extractTextFromElemList(articleElem.findall('./back'))
				floatingText = extractTextFromElemList(articleElem.findall('./floats-group'))

				referenceElems = articleElem.findall('./back/ref-list/ref')
				references = {}
				for r in referenceElems:
					# pub-id-type
					refIDs = {}
					refIDElems = r.findall('element-citation/pub-id') + r.findall('mixed-citation/pub-id')
					for rid in refIDElems:
						if 'pub-id-type' in rid.attrib:
							refIDs[rid.attrib['pub-id-type']] = rid.text

					references[r.attrib['id']] = refIDs

				document = {'pmid':subPmidText, 'pmcid':subPmcidText, 'doi':subDoiText, 'pubYear':subPubYear, 'pubMonth':subPubMonth, 'pubDay':subPubDay, 'journal':subJournal, 'journalISO':subJournalISO, 'references':references}

				textSources = {}
				textSources['title'] = titleText
				textSources['subtitle'] = subtitleText
				textSources['abstract'] = abstractText
				textSources['article'] = articleText
				textSources['back'] = backText
				textSources['floating'] = floatingText

				for k in textSources.keys():
					tmp = textSources[k]
					tmp = [ t for t in tmp if len(t) > 0 ]
					#tmp = [ html.unescape(t) for t in tmp ]
					tmp = [ removeBracketsWithoutWords(t) for t in tmp ]
					textSources[k] = tmp

				document['textSources'] = textSources
				yield document
		
			# Less important here (compared to abstracts) as each article file is not too big
			elem.clear()


allowedSubsections = {"abbreviations","additional information","analysis","author contributions","authors' contributions","authors’ contributions","background","case report","competing interests","conclusion","conclusions","conflict of interest","conflicts of interest","consent","data analysis","data collection","discussion","ethics statement","funding","introduction","limitations","material and methods","materials","materials and methods","measures","method","methods","participants","patients and methods","pre-publication history","related literature","results","results and discussion","statistical analyses","statistical analysis","statistical methods","statistics","study design","summary","supplementary data","supplementary information","supplementary material","supporting information"}
def pmcxml2bioc(source):
	try:
		currentID = 1
		for pmcDoc in processPMCFile(source):
			biocDoc = bioc.BioCDocument()
			biocDoc.id = pmcDoc["pmid"]

			biocDoc.infons['title'] = " ".join(pmcDoc["textSources"]["title"])
			biocDoc.infons['pmid'] = pmcDoc["pmid"]
			biocDoc.infons['pmcid'] = pmcDoc["pmcid"]
			biocDoc.infons['doi'] = pmcDoc["doi"]
			biocDoc.infons['year'] = pmcDoc["pubYear"]
			biocDoc.infons['month'] = pmcDoc["pubMonth"]
			biocDoc.infons['day'] = pmcDoc["pubDay"]
			biocDoc.infons['journal'] = pmcDoc["journal"]
			biocDoc.infons['journalISO'] = pmcDoc["journalISO"]

			offset = 0
			for groupName,textSourceGroup in pmcDoc["textSources"].items():
				subsection = None
				for textSource in textSourceGroup:
					textSource = trimSentenceLengths(textSource)

					#print(pmcDoc["pmcid"], textSource)

					textSource, annotations = extractAnnotations(textSource)

					passage = bioc.BioCPassage()

					subsectionCheck = textSource.lower().strip('01234567890. ')
					if subsectionCheck in allowedSubsections:
						subsection = subsectionCheck

					passage.infons['section'] = groupName
					passage.infons['subsection'] = subsection
					passage.text = textSource
					passage.offset = offset

					for anno in annotations:
						start,end = anno['position']

						a = bioc.BioCAnnotation()
						a.text = passage.text[start:end]
						a.infons = {k:v for k,v in anno.items() if k != 'position'}

						# Connect up references with document IDs (e.g. pmids)
						if anno['type'] == 'xref' and 'rid' in anno and anno['rid'] in pmcDoc['references']:
							a.infons.update(pmcDoc['references'][anno['rid']])

						#a.id = 'T%d' % currentID
						a.id = "%s_%d" % (anno['type'],currentID)
						currentID += 1

						if end <= start:
							continue

						biocLoc = bioc.BioCLocation(offset=passage.offset+start, length=(end-start))
						a.locations.append(biocLoc)
						passage.annotations.append(a)

					offset += len(textSource)
					biocDoc.add_passage(passage)

			yield biocDoc
			
	except etree.ParseError:
		raise RuntimeError("Parsing error in PMC xml file: %s" % source)	
