
import gzip
import sqlite3
import os
import hashlib
import io
import xml.etree.cElementTree as etree
import shutil
import sys
import time
import tempfile

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

def saveDocumentsToDatabase(db_filename, documents_filename, is_fulltext, file_index=-1):
	if os.path.isfile(db_filename):
		os.remove(db_filename)

	if not is_fulltext:
		assert file_index > 0, "Must provide the PubMed file number"

	con = sqlite3.connect(db_filename)
	
	cur = con.cursor()
	cur.execute("CREATE TABLE fulltext(pmid INTEGER PRIMARY KEY ASC, compressed BLOB, hash INTEGER, updated INTEGER);")
	con.commit()

	cur.execute("CREATE TABLE abstracts(pmid INTEGER PRIMARY KEY ASC, compressed BLOB, hash INTEGER, updated INTEGER, file_index INTEGER);")
	con.commit()

	timestamp = int(time.time())

	document_records = []
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
					
					original_hash = calcSHA256_AsInt(compressed)

					if is_fulltext:
						document_record = (pmid, compressed, original_hash, timestamp)
					else:
						document_record = (pmid, compressed, original_hash, timestamp, file_index)

					document_records.append(document_record)
				
				elem.clear()
		
	if is_fulltext:	
		cur.executemany("INSERT INTO fulltext VALUES (?,?,?,?)", document_records)
	else:
		cur.executemany("INSERT INTO abstracts VALUES (?,?,?,?,?)", document_records)

	con.commit()

	print("Stored %d {table} in database" % len(document_records))

	con.close()

def getDBSchema(db_filename):
	con = sqlite3.connect(db_filename)
	
	cur = con.cursor()

	cur.execute("SELECT name FROM sqlite_master WHERE type='table';")

	tables = [ row[0] for row in cur.fetchall() ]

	tables_with_columns = {}
	for table in tables:
		cur.execute("PRAGMA table_info(%s);" % table)
		tables_with_columns[table] = cur.fetchall()

	con.close()

	return tables_with_columns

def truncateFileAndKeepModifiedDates(filename):
	assert os.path.isfile(filename)

	access_time = os.path.getatime(filename)
	modification_time = os.path.getmtime(filename)

	with open(filename,'w'):
		pass

	os.utime(filename, (access_time, modification_time))

def mergeDBs(input_dbs,output_db,truncate_inputs=False):
	assert isinstance(input_dbs,list), "Expected list of input DB files"
	assert isinstance(output_db, str), "Expected string with output DB"

	input_dbs_orig = list(input_dbs)

	input_dbs = [ input_db for input_db in input_dbs if os.path.getsize(input_db) > 0 ]

	if len(input_dbs) < len(input_dbs_orig):
		skip_count = len(input_dbs_orig) - len(input_dbs)
		print("Skipping %d files that are empty" % skip_count)

	tmp_output_db = "%s.tmp" % output_db

	# If the output_db doesn't exist, use the first input db and merge into it
	if not os.path.isfile(output_db):
		assert len(input_dbs) > 0, "Must provide non-empty databases as no output file exists yet"
		print("Starting with %s..." % input_dbs[0])
		shutil.copyfile(input_dbs[0],tmp_output_db)
		input_dbs = input_dbs[1:]
	else:
		if len(input_dbs) == 0:
			print("No input databases to process, but output database does exist. So no work to do.")
			return
		shutil.copyfile(output_db,tmp_output_db)

	expected_schema = getDBSchema(tmp_output_db)

	con = sqlite3.connect(tmp_output_db)
	cur = con.cursor()

	for input_db in input_dbs:
		#if os.path.getsize(input_db) == 0:
		#	print("Skipping %s..." % input_db)
		#	continue

		assert os.path.getsize(input_db) > 0, "Input db file (%s) is empty" % input_db

		print("Processing %s..." % input_db)
		sys.stdout.flush()

		tmp_insert_db = "%s.tmp" % input_db

		shutil.copyfile(input_db, tmp_insert_db)

		input_schema = getDBSchema(tmp_insert_db)

		assert expected_schema == input_schema, "Databases should match up exactly! %s != %s" % (expected_schema, input_schema)


		cur.execute("ATTACH DATABASE ? as input_db ;", (tmp_insert_db, ))

		for table in ['fulltext','abstracts']:
			time_field = 'updated' if table == 'fulltext' else 'file_index'

			# Update the documents  table with the latest documents
			cur.execute(f"DELETE FROM input_db.{table} WHERE pmid IN (SELECT current.pmid FROM input_db.{table} inserting, {table} current WHERE inserting.pmid = current.pmid AND inserting.{time_field} < current.{time_field} AND inserting.hash != current.hash )")
			con.commit()

			cur.execute(f"DELETE FROM input_db.{table} WHERE pmid IN (SELECT current.pmid FROM input_db.{table} inserting, {table} current WHERE inserting.pmid = current.pmid AND inserting.{time_field} > current.{time_field} AND inserting.hash == current.hash )")
			con.commit()

			cur.execute(f"REPLACE INTO {table} SELECT * FROM input_db.{table};")
			con.commit()


		cur.execute("DETACH DATABASE input_db ;")
		
		con.commit()

		os.remove(tmp_insert_db)

	con.close()

	shutil.move(tmp_output_db,output_db)

	if truncate_inputs:
		for input_db in input_dbs_orig:
			truncateFileAndKeepModifiedDates(input_db)

