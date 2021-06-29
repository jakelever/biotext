import argparse
import sqlite3

def main():
	parser = argparse.ArgumentParser(description='Create an initial DB')
	parser.add_argument('--db',required=True,type=str,help='Name of DB file')
	args = parser.parse_args()
	
	assert args.db.endswith('.db')
	
	con = sqlite3.connect(args.db)
	
	cur = con.cursor()
	
	cur.execute("CREATE TABLE documents(pmid INTEGER PRIMARY KEY ASC, compressed BLOB);")
	
	con.commit()
	
	con.close()

if __name__ == '__main__':
	main()
