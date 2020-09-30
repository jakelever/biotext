
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

def download_file_with_retries(url, local_filename, retries=10):
	for tryno in range(retries):
		try:
			download_file_and_check_md5sum(url, local_filename)
			return
		except:
			print("Unexpected error:", sys.exc_info()[0])
			time.sleep(3*(tryno+1))

	raise RuntimeError("Unable to download %s" % url)

acceptedOutFormats = ['biocxml','txt']
if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Tool to convert corpus between different formats')
	parser.add_argument('--url',type=str,required=True,help="URL to PubMed GZipped XML file")
	parser.add_argument('--o',type=str,required=True,help="Where to store resulting converted docs")
	parser.add_argument('--oFormat',type=str,required=True,help="Format for output corpus. Options: %s" % "/".join(acceptedOutFormats))

	args = parser.parse_args()

	inFormat = 'pubmedxml'
	outFormat = args.oFormat.lower()

	assert outFormat in acceptedOutFormats, "%s is not an accepted output format. Options are: %s" % (outFormat, "/".join(acceptedOutFormats))

	with tempfile.NamedTemporaryFile() as tf:
		print("Downloading...")
		download_file_with_retries(args.url, tf.name)

		print("Converting...")
		with gzip.open(tf.name) as f:	
			convert([f],inFormat,args.o,outFormat)

	print("Output to %s complete" % args.o)

