import argparse
import sqlite3
import os
#import bioc
import sys
import xml.etree.cElementTree as etree

#from io import StringIO
import gzip
import io

def gzip_str(string_: str) -> bytes:
	out = io.BytesIO()

	with gzip.GzipFile(fileobj=out, mode='w') as fo:
		fo.write(string_.encode())

	bytes_obj = out.getvalue()
	return bytes_obj


def gunzip_bytes_obj(bytes_obj: bytes) -> str:
	return gzip.decompress(bytes_obj).decode()


def main():
	parser = argparse.ArgumentParser(description='Insert documents into DB')
	parser.add_argument('--db',required=True,type=str,help='Name of DB file')
	parser.add_argument('--inDir',required=True,type=str,help='Directory with BioC files')
	args = parser.parse_args()
	
	assert args.db.endswith('.db')
	
	pubmed_files = [ f for f in os.listdir(args.inDir) if f.endswith('.bioc.xml') and f.startswith('pubmed') ]
	pmc_files = [ f for f in os.listdir(args.inDir) if f.endswith('.bioc.xml') and f.startswith('pmc') ]
	
	input_files = sorted(pmc_files,reverse=True) + sorted(pubmed_files,reverse=True)
	
	
	con = sqlite3.connect(args.db)
	
	cur = con.cursor()
	
	seen_pmids = set()
	
	for input_file in input_files:
		print("Processing %s... [Loaded %d]" % (input_file,len(seen_pmids)))
		sys.stdout.flush()
		
		with open(os.path.join(args.inDir,input_file)) as f:
			records = []
		
			for event, elem in etree.iterparse(f, events=('start', 'end', 'start-ns', 'end-ns')):
				if (event=='end' and elem.tag=='document'):
					pmidField = elem.find('./id')
					if pmidField is None:
						elem.clear()
						continue
					pmid = pmidField.text
					if not pmid or pmid == 'None':
						elem.clear()
						continue
						
					pmid = int(pmid)
					
					if pmid in seen_pmids:
						elem.clear()
						continue
						
					seen_pmids.add(pmid)
					
					xmlstr = etree.tostring(elem, encoding='utf8', method='html').decode()
					#print(xmlstr)
					
					compressed = gzip_str(xmlstr)
					
					record = (pmid, compressed)
					records.append(record)
					
					
					elem.clear()
					
					#break
			
			cur.executemany("INSERT INTO documents VALUES (?,?)", records)
				
		#break

	
	if False:
		for input_file in input_files:
			print("Processing %s..." % input_file)
			sys.stdout.flush()
			
			with open(os.path.join(args.inDir,input_file),'rb') as f:
				#parser = bioc.BioCXMLDocumentReader(f)
				#for doc in parser:
					if not ('pmid' in doc.infons and doc.infons['pmid'] and doc.infons['pmid'] != 'None'):
						continue
						
					pmid = int(doc.infons['pmid'])
					
					
					
					bioc.dumps(doc)

					
					break
					
			break
	
	con.commit()
	
	con.close()

if __name__ == '__main__':
	main()
