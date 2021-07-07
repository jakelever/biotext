
import gzip
import sqlite3
import os
import hashlib
import io
import xml.etree.cElementTree as etree

def gzip_str(string_: str) -> bytes:
	out = io.BytesIO()

	with gzip.GzipFile(fileobj=out, mode='w') as fo:
		fo.write(string_.encode())

	bytes_obj = out.getvalue()
	return bytes_obj


def gunzip_bytes_obj(bytes_obj: bytes) -> str:
	return gzip.decompress(bytes_obj).decode()

def calcSHA256_AsInt(data):
	sha256 = hashlib.sha256(data).hexdigest()
	return int(sha256[:10],16)

def saveDocumentsToDatabase(db_filename, documents_filename, timestamp, is_fulltext):
	if os.path.isfile(db_filename):
		os.remove(db_filename)

	is_fulltext = 1 if bool(is_fulltext) else 0

	con = sqlite3.connect(db_filename)
	
	cur = con.cursor()
	cur.execute("CREATE TABLE documents(pmid INTEGER PRIMARY KEY ASC, compressed BLOB, is_fulltext INTEGER, original_hash INTEGER, has_pubtator_annotations INTEGER, pubtator_hash INTEGER, updated INTEGER);")
	con.commit()

	cur.execute("CREATE TABLE metadata(pmid INTEGER PRIMARY KEY ASC, compressed BLOB, hash INTEGER, updated INTEGER);")
	con.commit()



	document_records,metadata_records = [],[]
	seen_pmids = set()
	with open(documents_filename) as f:
		for event, elem in etree.iterparse(f, events=('start', 'end', 'start-ns', 'end-ns')):
			if (event=='end' and elem.tag=='document'):
				pmid_field = elem.find('./id')

				pmid = None
				if pmid_field is not None and pmid_field.text and pmid_field.text != 'None':
					pmid = int(pmid_field.text)
				
				if pmid and not pmid in seen_pmids:
					seen_pmids.add(pmid)
					
					xmlstr = etree.tostring(elem, encoding='utf8', method='html').decode()
				
					compressed = gzip_str(xmlstr)
					
					has_pubtator_annotations = 0
					original_hash = calcSHA256_AsInt(compressed)
					pubtator_hash = -1

					document_record = (pmid, compressed, is_fulltext, original_hash, has_pubtator_annotations, pubtator_hash, timestamp)
					document_records.append(document_record)

					if not is_fulltext: # Only gather metadata from PubMed
						metadata_fields = elem.findall('./infon')
						metadata_xmls = [ etree.tostring(mf, encoding='utf8', method='html').decode() for mf in metadata_fields ]
						metadata_singlexml = "<infons>%s</infons>" % "".join(metadata_xmls)
						metadata_compressed = gzip_str(metadata_singlexml)
						metadata_hash = calcSHA256_AsInt(metadata_compressed)

						metadata_record = (pmid, compressed, metadata_hash, timestamp)
						metadata_records.append(metadata_record)
						
						#print(metadata_fields)
						#assert False
				
				
				elem.clear()
			
	cur.executemany("INSERT INTO documents VALUES (?,?,?,?,?,?,?)", document_records)
	cur.executemany("INSERT INTO metadata VALUES (?,?,?,?)", metadata_records)

	con.commit()

	print("Stored %d documents in database" % len(document_records))

	con.close()

