import tarfile
import json

filename = '/scratch/users/jlever/non_comm_use.A-B.xml.tar.gz'

tar = tarfile.open(filename)

file_groups = {}
time_cutoff = 0

per_group = 30000

current_group = []

for i,member in enumerate(tar.getmembers()):
	#print(member, member.mtime)

	if member.isfile() and member.mtime > time_cutoff:
		current_group.append(member.name)

		if len(current_group) >= per_group:
			group_name = "%08d" % len(file_groups)
			file_groups[group_name] = current_group
			current_group = []

		#if i > 30000:
		#	break

with open('groups.json','w') as f:
	json.dump(file_groups,f)

