import argparse
import sys
import os
import shutil
import sqlite3

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

def main():
	parser = argparse.ArgumentParser('Merge document SQLite databases into a single database')
	parser.add_argument('--mainDB',required=True,type=str,help='Database to merge into')
	parser.add_argument('--inDir',required=True,type=str,help='Directory with SQLite databases to merge')
	args = parser.parse_args()

	input_dbs = sorted( os.path.join(args.inDir,f) for f in os.listdir(args.inDir) if f.endswith('.sqlite') )

	if len(input_dbs) == 0:
		print("No databases to merge.")
		sys.exit(0)

	if os.path.isfile(args.mainDB):
		print("DELETING the main DB, for testing purposes")
		os.remove(args.mainDB)

	if not os.path.isfile(args.mainDB):
		shutil.copyfile(input_dbs[0], args.mainDB)
		input_dbs = input_dbs[1:]

	main_schema = getDBSchema(args.mainDB)

	con = sqlite3.connect(args.mainDB)
	cur = con.cursor()

	#cur.execute("CREATE TABLE documents(pmid INTEGER PRIMARY KEY ASC, compressed BLOB, is_fulltext INTEGER, hash INTEGER, updated INTEGER);")
	
	for input_db in input_dbs:
		if os.path.getsize(input_db) == 0:
			print("Skipping %s..." % input_db)
			continue

		print("Processing %s..." % input_db)
		sys.stdout.flush()

		input_schema = getDBSchema(input_db)
		assert main_schema == input_schema, "Databases should match up exactly! %s != %s" % (main_schema, input_schema)


		cur.execute("ATTACH DATABASE ? as input_db ;", (input_db, ))

		# Update the documents table with the latest documents
		cur.execute("DELETE FROM input_db.documents WHERE pmid IN (SELECT d1.pmid FROM documents d1, input_db.documents d2 WHERE d1.pmid = d2.pmid AND d1.original_hash == d2.original_hash)")
		con.commit()

		cur.execute("DELETE FROM input_db.documents WHERE is_fulltext = 0 AND pmid IN (SELECT pmid FROM documents WHERE is_fulltext = 1);")
		con.commit()

		cur.execute("REPLACE INTO documents SELECT * FROM input_db.documents;")
		con.commit()

		# Update the metadata table with the latest metadata
		cur.execute("DELETE FROM input_db.metadata WHERE pmid IN (SELECT m1.pmid FROM metadata m1, input_db.metadata m2 WHERE m1.pmid = m2.pmid AND m1.hash == m2.hash)")
		con.commit()

		cur.execute("REPLACE INTO metadata SELECT * FROM input_db.metadata;")
		con.commit()

		cur.execute("DETACH DATABASE input_db ;")
		
		con.commit()

	con.close()

if __name__ == '__main__':
	main()

