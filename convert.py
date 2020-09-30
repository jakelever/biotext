
import argparse

from bioconverters import convert

acceptedInFormats = ['biocxml','pubmedxml','marcxml','pmcxml','uimaxmi']
acceptedOutFormats = ['biocxml','txt']
if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Tool to convert corpus between different formats')
	parser.add_argument('--i',type=str,required=True,help="Comma-delimited list of documents to convert")
	parser.add_argument('--iFormat',type=str,required=True,help="Format of input corpus. Options: %s" % "/".join(acceptedInFormats))
	parser.add_argument('--o',type=str,required=True,help="Where to store resulting converted docs")
	parser.add_argument('--oFormat',type=str,required=True,help="Format for output corpus. Options: %s" % "/".join(acceptedOutFormats))

	args = parser.parse_args()

	inFormat = args.iFormat.lower()
	outFormat = args.oFormat.lower()

	assert inFormat in acceptedInFormats, "%s is not an accepted input format. Options are: %s" % (inFormat, "/".join(acceptedInFormats))
	assert outFormat in acceptedOutFormats, "%s is not an accepted output format. Options are: %s" % (outFormat, "/".join(acceptedOutFormats))

	inFiles = args.i.split(',')
	
	print("Converting %d files to %s" % (len(inFiles),args.o))
	convert(inFiles,inFormat,args.o,outFormat)
	print("Output to %s complete" % args.o)

