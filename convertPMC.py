import argparse
import os
import json
import tarfile

from bioconverters import pmcxml2bioc
import bioc
import io

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Convert a block of PMC articles')
	parser.add_argument('--pmcDir',required=True,type=str,help='Directory with PMC Tar Gz files and groupings already processed')
	parser.add_argument('--block',required=True,type=str,help='Name of block to process')
	parser.add_argument('--format',required=True,type=str,help='Format to output documents to (only biocxml supported)')
	parser.add_argument('--outFile',required=True,type=str,help='File to save to')
	args = parser.parse_args()

	assert args.format == 'biocxml'

	grouping_file = os.path.join(args.pmcDir,'groupings.json')
	with open(grouping_file) as f:
		block = json.load(f)['groups'][args.block]

	source = os.path.join(args.pmcDir, block['src'])
	files_to_extract = block['group']

	#print(source)
	#print(len(files_to_extract))

	with bioc.BioCXMLDocumentWriter(args.outFile) as writer:
		tar = tarfile.open(source)
		for i,filename in enumerate(files_to_extract):
			#print(i,filename)
			member = tar.getmember(filename)
			#print(member)
			file_handle = tar.extractfile(member)
			#print(file_handle)
			data = file_handle.read().decode('utf-8')
			#print(len(data))
			#print(data[:500])
			for biocDoc in pmcxml2bioc(io.StringIO(data)):
				writer.write_document(biocDoc)

			#break
	print("Saved %d documents to %s" % (len(files_to_extract), args.outFile))

