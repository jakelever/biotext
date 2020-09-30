import tarfile
import json
import argparse
import os

if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Split up the documents inside a PMC archive into groups and save the groupings')
	parser.add_argument('--inPMC',required=True,type=str,help='Gzipped Tar with PubMedCentral documents')
	parser.add_argument('--prevGroupings',required=False,type=str,help='Previous groupings file to extend')
	parser.add_argument('--outGroupings',required=True,type=str,help='JSON file with output groupings')
	args = parser.parse_args()

	per_group = 30000

	print("Splitting PMC archive into groups of %d documents" % per_group)

	tar = tarfile.open(args.inPMC)

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

	current_group = []

	for i,member in enumerate(tar.getmembers()):
		if member.isfile() and member.name.endswith('.nxml') and member.mtime > time_cutoff:
			current_group.append(member.name)

			if member.mtime > newest_mtime:
				newest_mtime = member.mtime

			if len(current_group) >= per_group:
				group_name = "%08d" % len(file_groups)
				file_groups[group_name] = current_group
				current_group = []

			#if i > 30000:
			#	break
	if len(current_group) > 0:
		group_name = "%08d" % len(file_groups)
		file_groups[group_name] = current_group
	
	print("Added %d new groups" % (len(file_groups)-prev_group_count))

	output = {'mtime':newest_mtime, 'groups':file_groups}
	with open(args.outGroupings,'w') as f:
		json.dump(output,f)

