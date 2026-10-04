import argparse
import io
import json
import urllib.parse

import bioc
from bioconverters import pmcxml2bioc

from s3util import get_anonymous_s3_client, fetch_object_text
from fileutil import open_maybe_gzip

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Convert a batch of PMC articles fetched from the PMC Cloud Service (S3)')
	parser.add_argument('--batchesFile',required=True,type=str,help='JSON file mapping batch names to lists of s3:// article XML URIs')
	parser.add_argument('--batch',required=True,type=str,help='Name of batch to process')
	parser.add_argument('--outFile',required=True,type=str,help='File to save to (gzipped if it ends with .gz)')
	parser.add_argument('--region',required=False,type=str,default='us-east-1',help='AWS region for the S3 client')
	parser.add_argument('--endpointUrl',required=False,type=str,default=None,help='Override S3 endpoint URL (for testing against a local fake S3)')
	parser.add_argument('--verbose',action='store_true',help="Whether to provide more output")
	args = parser.parse_args()

	with open(args.batchesFile) as f:
		uris = json.load(f)[args.batch]

	print(f"Fetching {len(uris)} documents from S3 for batch {args.batch}")

	client = get_anonymous_s3_client(region=args.region, endpoint_url=args.endpointUrl)

	with open_maybe_gzip(args.outFile, 'wb') as f_out, bioc.biocxml.iterwrite(f_out) as writer:
		for i, uri in enumerate(uris):
			parsed = urllib.parse.urlparse(uri)
			assert parsed.scheme == 's3', f"Expected an s3:// URI, got: {uri}"
			bucket, key = parsed.netloc, parsed.path.lstrip('/')

			if args.verbose:
				print(f"Fetching {i + 1}/{len(uris)}: {uri}")

			try:
				data = fetch_object_text(client, bucket, key)
			except FileNotFoundError as e:
				print(f"WARNING: skipping missing object: {e}")
				continue

			for bioc_doc in pmcxml2bioc(io.StringIO(data)):
				writer.write_document(bioc_doc)

	print("Saved %d documents to %s" % (len(uris), args.outFile))
