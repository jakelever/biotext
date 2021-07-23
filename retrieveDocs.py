import argparse
import sqlite3
import os
import sys
import xml.etree.cElementTree as etree

import gzip
import io
import subprocess
import json

from dbutils import gunzip_bytes_obj

import xml.etree.ElementTree as ET

def pretty_print_xml(xml):
	proc = subprocess.Popen(
		['xmllint', '--format', '-'],
		stdin=subprocess.PIPE,
		stdout=subprocess.PIPE,
	)
	(output, error_output) = proc.communicate(xml.encode());
	return output

def mergeInMetadata(fulltext,abstract):
	fulltext_root = ET.fromstring(fulltext)
	abstract_root = ET.fromstring(abstract)

	assert list(fulltext_root)[0].tag == 'id', "Expected first tag of document to be the id"

	# Removing the metadata from the full text document
	for infon in fulltext_root.findall('./infon'):
		fulltext_root.remove(infon)

	# Copying over the metadata from the PubMed/abstract to the full text document
	for infon in reversed(abstract_root.findall('./infon')):
		fulltext_root.insert(1,infon)

	xmlstr = ET.tostring(fulltext_root, encoding='utf8', method='html').decode()
	return xmlstr

def main():
	parser = argparse.ArgumentParser(description='Insert documents into DB')
	parser.add_argument('--db',required=True,type=str,help='Name of DB file')
	parser.add_argument('--list',action='store_true',help='List out document info stored in the database (instead of anything else)')
	parser.add_argument('--mode',required=True,type=str,help='Whether to get abstracts/fulltext or whichever is available (abstracts/fulltext/all)')
	parser.add_argument('--pmids',required=False,type=str,help='Comma-delimited set of pmids')
	parser.add_argument('--pmidfile',required=False,type=str,help='File with PMIDs. Either JSON file or text file with one PMID per line')
	parser.add_argument('--noprettyify',action='store_true',help='Do not prettyify the output BioC document')
	parser.add_argument('--outFile',required=True,type=str,help='Output file')
	args = parser.parse_args()
	
	con = sqlite3.connect(args.db)	
	cur = con.cursor()

	if args.list:
		fulltext_count,abstract_count = 0,0
		with open(args.outFile,'w') as outF:
			outF.write("type\tpmid\thash\tupdated\tfile_index\n")
			for pmid,hash_value,updated,file_index in cur.execute('SELECT pmid,hash,updated,file_index FROM abstracts ORDER BY pmid'):
				outF.write("%s\t%d\t%d\t%d\t%d\n" % ("abstract",pmid,hash_value,updated,file_index))
				abstract_count += 1
			for pmid,hash_value,updated in cur.execute('SELECT pmid,hash,updated FROM fulltext ORDER BY pmid'):
				outF.write("%s\t%d\t%d\t%d\t%d\n" % ("fulltext",pmid,hash_value,updated,-1))
				fulltext_count += 1
		
		print("Saved listing of %d full-text documents and %d abstracts" % (fulltext_count,abstract_count))
		sys.exit(0)

	assert args.pmids or args.pmidfile, "Must provide --pmids or --pmidfile"
	assert not(args.pmids and args.pmidfile), "Must provide only one of --pmids or --pmidfile"

	assert args.mode in ['abstracts','fulltext','all']

	pmids = []
	if args.pmids:
		pmids = args.pmids.split(',')
	elif args.pmidfile:
		with open(args.pmidfile) as f:
			if args.pmidfile.endswith('.json'):
				pmids = json.load(f)
			else:
				pmids = [ line.strip() for line in f ]

	pmids = [ pmid for pmid in pmids if pmid ]
	
	written = 0
	with open(args.outFile,'w') as outF:
		outF.write('<?xml version="1.0" encoding="utf8" standalone="yes"?>\n<collection>\n')
		for pmid in pmids:

			abstract,fulltext = None,None

			cur.execute('SELECT compressed FROM abstracts WHERE pmid = ?', (pmid,))
			abstract = cur.fetchone()
			if abstract:
				abstract = gunzip_bytes_obj(abstract[0])

			if args.mode in ['fulltext','all']:
				cur.execute('SELECT compressed FROM fulltext WHERE pmid = ?', (pmid,))
				fulltext = cur.fetchone()
				if fulltext:
					fulltext = gunzip_bytes_obj(fulltext[0])

					# Let's pull over some metadata from the PubMed data
					if abstract:
						fulltext = mergeInMetadata(fulltext,abstract)


			if args.mode == 'abstracts':
				out_doc = abstract
			elif args.mode == 'fulltext':
				out_doc = fulltext
			elif args.mode == 'all':
				out_doc = fulltext if fulltext else abstract


			if out_doc is None:
				print("WARNING: No document found with PMID=%s" % pmid)
				continue
			
			outF.write(out_doc)

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

