import argparse
import sys
import os
import shutil
import sqlite3

from dbutils import mergeDBs

def main():
	parser = argparse.ArgumentParser('Merge document SQLite databases into a single database')
	parser.add_argument('--mainDB',required=True,type=str,help='Database to merge into')
	parser.add_argument('--inDir',required=True,type=str,help='Directory with SQLite databases to merge')
	parser.add_argument('--truncateInputs',action='store_true',help='Whether to truncate the input files (to save disk space)')
	args = parser.parse_args()

	truncate_inputs = bool(args.truncateInputs)

	input_dbs = sorted( os.path.join(args.inDir,f) for f in os.listdir(args.inDir) if f.endswith('.sqlite') )

	#if len(input_dbs) == 0:
	#	print("No databases to merge.")
	#	sys.exit(0)

	#if os.path.isfile(args.mainDB):
	#	print("DELETING the main DB, for testing purposes")
	#	os.remove(args.mainDB)

	mergeDBs(input_dbs,args.mainDB,truncate_inputs)

if __name__ == '__main__':
	main()

