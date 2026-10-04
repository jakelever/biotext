
import argparse
from Bio import Entrez
import io

import bioc
from bioconverters import pmcxml2bioc, pubmedxml2bioc

from fileutil import open_maybe_gzip


acceptedOutFormats = ['biocxml']
if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Downloads and converts small number of PubMed or PubMed Central documents. Useful for testing purposes.')
	parser.add_argument('--database',type=str,required=True,help="Which database to use (pubmed/pmc)")
	parser.add_argument('--identifiers',type=str,required=True,help="PubMed or PMC identifiers (comma-delimited). Max of 10.")
	parser.add_argument('--email',type=str,required=True,help="Entrez requires an email address is provided to use their API")
	parser.add_argument('--o',type=str,required=True,help="Where to store resulting converted docs (gzipped if it ends with .gz)")
	parser.add_argument('--oFormat',type=str,required=True,help="Format for output corpus. Options: %s" % "/".join(acceptedOutFormats))

	args = parser.parse_args()

	Entrez.email = args.email

	assert args.database in ['pubmed','pmc'], "Database must be pubmed or pmc"
	identifiers = args.identifiers.split(',')
	assert len(identifiers) <= 10, "Too many identifiers provided. The EUtils API should only be used for a small number of documents"

	parse_func = pubmedxml2bioc if args.database == "pubmed" else pmcxml2bioc

	doc_xmls = []
	for identifier in identifiers:
		handle = Entrez.efetch(db=args.database, id=identifier, rettype="gb", retmode="xml")
		doc_xml = io.StringIO(handle.read().decode('utf-8'))
		doc_xmls.append(doc_xml)

	outFormat = args.oFormat.lower()
	assert outFormat in acceptedOutFormats, "%s is not an accepted output format. Options are: %s" % (outFormat, "/".join(acceptedOutFormats))

	print("Fetching and converting %d files from %s" % (len(doc_xmls),args.database))
	with open_maybe_gzip(args.o, 'wb') as f, bioc.biocxml.iterwrite(f) as writer:
		for doc_xml in doc_xmls:
			for bioc_doc in parse_func(doc_xml):
				writer.write_document(bioc_doc)
	print("Output to %s complete" % args.o)

