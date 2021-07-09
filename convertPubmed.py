
import argparse
import tempfile
import hashlib

from bioconverters import convert

import shutil
import urllib.request as request
from contextlib import closing
import time
import gzip
import sys
import string

import re
import os
from datetime import datetime

from dbutils import saveDocumentsToDatabase

def download_file(url,local_filename):
	with closing(request.urlopen(url)) as r:
		with open(local_filename, 'wb') as f:
			shutil.copyfileobj(r, f)

def download_file_and_check_md5sum(url, local_filename):
	with tempfile.NamedTemporaryFile() as tf:
		md5_url = "%s.md5" % url
		download_file(md5_url, tf.name)
		
		with open(tf.name) as f:
			expected_md5 = f.read().strip()
			assert expected_md5.startswith('MD5(') and '=' in expected_md5
			expected_md5 = expected_md5.split('=')[1].strip()
		#print("expected:", expected_md5)

	download_file(url, local_filename)
	with open(local_filename,'rb') as f:
		got_md5 = hashlib.md5(f.read()).hexdigest()
	#print("got:", got_md5)

	if expected_md5 != got_md5:
		raise RuntimeError("MD5 of downloaded file doesn't match expected: %s != %s" % (expected_md5,got_md5))

def download_file_with_retries(url, local_filename, check_md5=False, retries=10):
	for tryno in range(retries):
		try:
			if check_md5:
				download_file_and_check_md5sum(url, local_filename)
			else:
				download_file(url,local_filename)
			return
		except:
			print("Unexpected error:", sys.exc_info()[0], sys.exc_info()[1])
			time.sleep(5*(tryno+1))

	raise RuntimeError("Unable to download %s" % url)


def get_pubmed_timestamp(url):
	assert url.startswith('ftp://ftp.ncbi.nlm.nih.gov/pubmed/')

	listing_url = os.path.dirname(url).replace('ftp://','http://')
	filename = os.path.basename(url)

	with tempfile.NamedTemporaryFile() as tf:
		download_file_with_retries(listing_url,tf.name)
		with open(tf.name) as f:
			listing_page = f.read()

	match = re.search('<a href="%s">%s</a>\s+(\d+-\d+-\d+\s+\d+:\d+)' % (filename,filename), listing_page)
	assert match, "Could not find timestamp for url: %s" % url
    
	found_date = match.groups()[0]
	date_obj = datetime.strptime(found_date, '%Y-%m-%d %H:%M')
	timestamp = int(datetime.timestamp(date_obj))

	return timestamp

def get_pubmed_fileindex(url):
	filename = os.path.basename(url)
	digits_in_filename = [ c for c in filename if c in string.digits ]
	assert len(digits_in_filename) == 6, "Expected exactly 6 digits in filename: %s" % filename
	file_index = int("".join(digits_in_filename))
	return int(file_index)
	

accepted_out_formats = ['biocxml','txt']
def main():
	parser = argparse.ArgumentParser(description='Tool to convert corpus between different formats')
	parser.add_argument('--url',type=str,required=True,help="URL to PubMed GZipped XML file")
	parser.add_argument('--o',type=str,required=True,help="Where to store resulting converted docs")
	parser.add_argument('--oFormat',type=str,required=True,help="Format for output corpus. Options: %s" % "/".join(accepted_out_formats))
	parser.add_argument('--db',action='store_true',help="Whether to output as an SQLite database")

	args = parser.parse_args()

	in_format = 'pubmedxml'
	out_format = args.oFormat.lower()

	if args.db:
		assert out_format == 'biocxml', "Output format must be biocxml when storing to the database"

	assert out_format in accepted_out_formats, "%s is not an accepted output format. Options are: %s" % (out_format, "/".join(accepted_out_formats))

	file_index = get_pubmed_fileindex(args.url)

	with tempfile.NamedTemporaryFile() as tf_pubmed, tempfile.NamedTemporaryFile() as tf_out:
		print("Downloading...")
		download_file_with_retries(args.url, tf_pubmed.name, check_md5=True)
	
		out_file = tf_out.name if args.db else args.o

		print("Converting...")
		with gzip.open(tf_pubmed.name) as f:	
			convert([f],in_format,out_file,out_format)

		if args.db:
			saveDocumentsToDatabase(args.o,tf_out.name,is_fulltext=False,file_index=file_index)

	print("Output to %s complete" % args.o)

if __name__ == '__main__':
	main()

