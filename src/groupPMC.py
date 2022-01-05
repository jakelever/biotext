import tarfile
import json
import argparse
import os
import sys

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Split up the documents inside a set of PMC archives into groups and save the groupings')
	parser.add_argument('--inPMCDir',required=True,type=str,help='Directory with gzipped tars of PubMedCentral documents')
	parser.add_argument('--prevGroupings',required=False,type=str,help='Previous groupings file to extend')
	parser.add_argument('--outGroupings',required=True,type=str,help='JSON file with output groupings')
	args = parser.parse_args()

	per_group = 2000

	print("Splitting PMC archive into groups of %d documents" % per_group)

	if args.prevGroupings and os.path.isfile(args.prevGroupings):
		with open(args.prevGroupings) as f:
			prev = json.load(f)

		file_groups = prev['groups']
		prev_group_count = len(file_groups)
		time_cutoff = prev['mtime']
		newest_mtime = prev['mtime']

		print("Loaded %d existing groups" % prev_group_count)
	else:	
		file_groups = {}
		prev_group_count = 0
		time_cutoff = 0
		newest_mtime = 0

	gztarFiles = sorted([ f for f in os.listdir(args.inPMCDir) if f.endswith('.tar.gz') ])

	for filename in gztarFiles:
		print("Processing %s" % filename)
		sys.stdout.flush()

		tar = tarfile.open(os.path.join(args.inPMCDir,filename))
		current_group = []

		for i,member in enumerate(tar.getmembers()):
			file_ext = member.name.split('.')[-1]
			if member.isfile() and file_ext in ['xml','nxml'] and member.mtime > time_cutoff:
				current_group.append(member.name)

				if member.mtime > newest_mtime:
					newest_mtime = member.mtime

				if len(current_group) >= per_group:
					group_name = "%08d" % len(file_groups)
					file_groups[group_name] = {'src':filename, 'group':current_group}
					current_group = []

		if len(current_group) > 0:
			group_name = "%08d" % len(file_groups)
			file_groups[group_name] = current_group
			file_groups[group_name] = {'src':filename, 'group':current_group}
			current_group = []

		tar.close()
	
	print("Added %d new groups" % (len(file_groups)-prev_group_count))

	output = {'mtime':newest_mtime, 'groups':file_groups}
	with open(args.outGroupings,'w') as f:
		json.dump(output,f)

