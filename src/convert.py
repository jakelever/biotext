import argparse

import bioc
from bioconverters import pmcxml2bioc, pubmedxml2bioc

from fileutil import open_maybe_gzip

acceptedInFormats = ['biocxml','pubmedxml','pmcxml']
acceptedOutFormats = ['biocxml']


def _bioc_docs_from_file(in_file, in_format):
	if in_format == 'pubmedxml':
		yield from pubmedxml2bioc(in_file)
	elif in_format == 'pmcxml':
		yield from pmcxml2bioc(in_file)
	elif in_format == 'biocxml':
		with open_maybe_gzip(in_file, 'rb') as f, bioc.biocxml.iterparse(f) as reader:
			yield from reader


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Tool to convert corpus between different formats')
	parser.add_argument('--i',type=str,required=True,help="Comma-delimited list of documents to convert")
	parser.add_argument('--iFormat',type=str,required=True,help="Format of input corpus. Options: %s" % "/".join(acceptedInFormats))
	parser.add_argument('--o',type=str,required=True,help="Where to store resulting converted docs (gzipped if it ends with .gz)")
	parser.add_argument('--oFormat',type=str,required=True,help="Format for output corpus. Options: %s" % "/".join(acceptedOutFormats))

	args = parser.parse_args()

	inFormat = args.iFormat.lower()
	outFormat = args.oFormat.lower()

	assert inFormat in acceptedInFormats, "%s is not an accepted input format. Options are: %s" % (inFormat, "/".join(acceptedInFormats))
	assert outFormat in acceptedOutFormats, "%s is not an accepted output format. Options are: %s" % (outFormat, "/".join(acceptedOutFormats))

	inFiles = args.i.split(',')

	print("Converting %d files to %s" % (len(inFiles),args.o))
	with open_maybe_gzip(args.o, 'wb') as f, bioc.biocxml.iterwrite(f) as writer:
		for in_file in inFiles:
			for bioc_doc in _bioc_docs_from_file(in_file, inFormat):
				writer.write_document(bioc_doc)
	print("Output to %s complete" % args.o)
