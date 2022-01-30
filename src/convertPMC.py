import argparse
import os
import json
import tarfile

from bioconverters import pmcxml2bioc
import bioc
import io

import tempfile
from dbutils import saveDocumentsToDatabase
import pathlib
from tqdm import tqdm

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Convert a block of PMC articles')
	parser.add_argument('--pmcDir',required=True,type=str,help='Directory with PMC Tar Gz files and groupings already processed')
	parser.add_argument('--block',required=True,type=str,help='Name of block to process')
	parser.add_argument('--format',required=True,type=str,help='Format to output documents to (only biocxml supported)')
	parser.add_argument('--outFile',required=True,type=str,help='File to save to')
	parser.add_argument('--db',action='store_true',help="Whether to output as an SQLite database")
	parser.add_argument('--verbose',action='store_true',help="Whether to provide more output")
	args = parser.parse_args()

	assert args.format == 'biocxml'

	grouping_file = os.path.join(args.pmcDir,'groupings.json')
	with open(grouping_file) as f:
		block = json.load(f)['groups'][args.block]

	source = os.path.join(args.pmcDir, block['src'])
	files_to_extract = block['group']

	print(f"Loading {len(files_to_extract)} documents from archive: {source}")

	with tempfile.NamedTemporaryFile() as tf_out:
		out_file = tf_out.name if args.db else args.outFile
		with bioc.BioCXMLDocumentWriter(out_file) as writer:
			tar = tarfile.open(source)

			iterator = tqdm(files_to_extract) if args.verbose else files_to_extract

			for filename in iterator:
				if args.verbose:
					iterator.set_description(filename)

				try:
					member = tar.getmember(filename)
				except KeyError:
					print("WARNING. Didn't find %s in %s. Skipping" % (filename,source))
					continue
				
				file_handle = tar.extractfile(member)
				
				data = file_handle.read().decode('utf-8')

				for bioc_doc in pmcxml2bioc(io.StringIO(data)):
					writer.write_document(bioc_doc)

		if args.db:
			saveDocumentsToDatabase(args.outFile,tf_out.name,is_fulltext=True)

	print("Saved %d documents to %s" % (len(files_to_extract), args.outFile))

