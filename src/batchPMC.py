import argparse
import json
import os
import re

BATCH_NAME_PATTERN = re.compile(r"^batch_(\d+)$")


def compute_new_batches(already_batched, all_keys, batch_size, start_index):
	new_keys = sorted(k for k in all_keys if k not in already_batched)

	batches = {}
	index = start_index
	for i in range(0, len(new_keys), batch_size):
		batch_name = "batch_%06d" % index
		batches[batch_name] = new_keys[i:i + batch_size]
		index += 1

	return batches


def next_batch_index(existing_batch_names):
	indices = [int(m.group(1)) for name in existing_batch_names for m in [BATCH_NAME_PATTERN.match(name)] if m]
	return (max(indices) + 1) if indices else 1


def main():
	parser = argparse.ArgumentParser(description="Split unprocessed PMC article keys into batches for parallel conversion")
	parser.add_argument("--keysFile", required=True, type=str, help="Listing file of s3:// PMC article XML URIs, one per line")
	parser.add_argument("--prevBatches", required=False, type=str, help="Previous batches JSON file to extend")
	parser.add_argument("--outBatches", required=True, type=str, help="JSON file with output batches")
	parser.add_argument("--batchSize", required=False, type=int, default=2000, help="Number of documents per batch")
	args = parser.parse_args()

	with open(args.keysFile) as f:
		all_keys = [line.strip() for line in f if line.strip()]

	if args.prevBatches and os.path.isfile(args.prevBatches):
		with open(args.prevBatches) as f:
			batches = json.load(f)
		print("Loaded %d existing batches" % len(batches))
	else:
		batches = {}

	already_batched = set(key for keys in batches.values() for key in keys)
	start_index = next_batch_index(batches.keys())

	new_batches = compute_new_batches(already_batched, all_keys, args.batchSize, start_index)
	batches.update(new_batches)

	print("Added %d new batches (%d new documents)" % (len(new_batches), sum(len(v) for v in new_batches.values())))

	with open(args.outBatches, "w") as f:
		json.dump(batches, f, sort_keys=True)


if __name__ == "__main__":
	main()
