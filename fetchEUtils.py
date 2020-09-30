
import argparse
from Bio import Entrez

acceptedInFormats = ['biocxml','pubmedxml','marcxml','pmcxml','uimaxmi']
acceptedOutFormats = ['biocxml','txt']
if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Downloads a single PubMed or PubMed Central document. Useful for testing purposes.')
	parser.add_argument('--database',type=str,required=True,help="Which database to use (pubmed/pmc)")
	parser.add_argument('--identifier',type=str,required=True,help="PubMed or PMC identifier")
	parser.add_argument('--email',type=str,required=True,help="Entrez requires an email address is provided to use their API")
	parser.add_argument('--o',type=str,required=True,help="Where to store the doc")

	args = parser.parse_args()

	Entrez.email = args.email

	assert args.database in ['pubmed','pmc'], "Database must be pubmed or pmc"

	with open(args.o,'w') as f:
		handle = Entrez.efetch(db=args.database, id=args.identifier, rettype="gb", retmode="xml")
		f.write(handle.read().decode('utf-8'))

	print("Output to %s complete" % args.o)

