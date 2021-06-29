import argparse
import sqlite3
import os
import sys
import xml.etree.cElementTree as etree

import gzip
import io
import subprocess

def gzipString(s):
	out = StringIO()
	with gzip.GzipFile(fileobj=out, mode="w") as f:
		f.write(s)
	return out.getvalue()
	
def gunzipString(text):
	infile = StringIO.StringIO()
	infile.write(text)
	with gzip.GzipFile(fileobj=infile, mode="r") as f:
		f.rewind()
		f.read()
	return out.getvalue()
	
def gzip_str(string_: str) -> bytes:
	out = io.BytesIO()

	with gzip.GzipFile(fileobj=out, mode='w') as fo:
		fo.write(string_)

	bytes_obj = out.getvalue()
	return bytes_obj


def gunzip_bytes_obj(bytes_obj: bytes) -> str:
	return gzip.decompress(bytes_obj).decode()

def pretty_print_xml(xml):
	proc = subprocess.Popen(
		['xmllint', '--format', '-'],
		stdin=subprocess.PIPE,
		stdout=subprocess.PIPE,
	)
	(output, error_output) = proc.communicate(xml.encode());
	return output

def main():
	parser = argparse.ArgumentParser(description='Insert documents into DB')
	parser.add_argument('--db',required=True,type=str,help='Name of DB file')
	parser.add_argument('--pmids',required=False,type=str,help='Comma-delimited set of pmids')
	parser.add_argument('--pmidfile',required=False,type=str,help='File with lines of PMIDs')
	parser.add_argument('--noprettyify',action='store_true',help='Do not prettyify the output BioC document')
	parser.add_argument('--outFile',required=True,type=str,help='Output file')
	args = parser.parse_args()
	
	assert args.db.endswith('.db')

	assert args.pmids or args.pmidfile, "Must provide --pmids or --pmidfile"
	assert not(args.pmids and args.pmidfile), "Must provide only one of --pmids or --pmidfile"

	pmids = []
	if args.pmids:
		pmids = args.pmids.split(',')
	elif args.pmidfile:
		with open(args.pmidfile) as f:
			pmids = [ line.strip() for line in f ]

	pmids = [ pmid for pmid in pmids if pmid ]
	
	con = sqlite3.connect(args.db)
	
	cur = con.cursor()
	
	written = 0
	with open(args.outFile,'w') as outF:
		outF.write('<?xml version="1.0" encoding="utf8" standalone="yes"?>\n<collection>\n')
		for pmid in pmids:
			cur.execute('SELECT pmid,compressed FROM documents WHERE pmid = ?', (pmid,))
			row = cur.fetchone()
			if row is None:
				print("WARNING: No document found with PMID=%s" % pmid)
				continue
				
			pmid,compressed = row
			
			xmlstr = gunzip_bytes_obj(compressed)
			
			outF.write(xmlstr)

			written += 1
		outF.write('</collection>\n')

	con.close()

	if not args.noprettyify:
		print("Prettyifying XML...")
		with open(args.outFile) as f:
			xml = f.read()
		with open(args.outFile,'wb') as outF:
			outF.write(pretty_print_xml(xml))

	print("Retrived documents for %d/%d provided PMIDs" % (written,len(pmids)))

if __name__ == '__main__':
	main()
