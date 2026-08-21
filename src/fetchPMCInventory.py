import argparse
import csv
import gzip
import io
import json
import os
import re
import sys
import time

from s3util import get_anonymous_s3_client, fetch_object_text

# PMC Cloud Service inventory objects list JSON metadata keys like
# "metadata/PMC13283695.1.json". The article's actual XML lives under a
# separate per-article-version prefix, e.g. "PMC13283695.1/PMC13283695.1.xml"
# (verified against the live pmc-oa-opendata bucket, not a same-prefix
# substitution as the JSON's own field names might suggest).
METADATA_PREFIX = "metadata/"
METADATA_SUFFIX = ".json"

CYCLE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}Z/$")


def derive_xml_key(metadata_key):
	if not metadata_key.startswith(METADATA_PREFIX) or not metadata_key.endswith(METADATA_SUFFIX):
		return None
	base = metadata_key[len(METADATA_PREFIX):-len(METADATA_SUFFIX)]
	if not base:
		return None
	return "%s/%s.xml" % (base, base)


def find_latest_cycle_prefix(common_prefixes, inventory_prefix):
	candidates = []
	for prefix in common_prefixes:
		assert prefix.startswith(inventory_prefix), "Unexpected common prefix %s outside of %s" % (prefix, inventory_prefix)
		suffix = prefix[len(inventory_prefix):]
		if CYCLE_PATTERN.match(suffix):
			candidates.append(prefix)

	assert candidates, "No dated inventory cycle folders found under %s" % inventory_prefix
	return sorted(candidates)[-1]


def parse_manifest(manifest):
	columns = [c.strip() for c in manifest["fileSchema"].split(",")]
	assert "Key" in columns, "Inventory manifest fileSchema did not contain a 'Key' column: %s" % columns
	key_column_index = columns.index("Key")

	part_keys = [f["key"] for f in manifest["files"]]
	assert part_keys, "Inventory manifest listed no CSV parts"

	return key_column_index, part_keys


def process_inventory_part(client, bucket, part_key, key_column_index, retries=5):
	for tryno in range(retries):
		try:
			response = client.get_object(Bucket=bucket, Key=part_key)
			xml_keys = []
			with gzip.GzipFile(fileobj=response["Body"]) as gz:
				text_stream = io.TextIOWrapper(gz, encoding="utf-8")
				for row in csv.reader(text_stream):
					xml_key = derive_xml_key(row[key_column_index])
					if xml_key:
						xml_keys.append(xml_key)
			return xml_keys
		except Exception:
			print("Unexpected error (%s %s) on try %d/%d while processing inventory part s3://%s/%s" % (sys.exc_info()[0], sys.exc_info()[1], tryno + 1, retries, bucket, part_key))
			time.sleep(5 * (tryno + 1))

	raise RuntimeError("Unable to process inventory part s3://%s/%s" % (bucket, part_key))


def list_cycle_prefixes(client, bucket, inventory_prefix):
	common_prefixes = []
	paginator = client.get_paginator("list_objects_v2")
	for page in paginator.paginate(Bucket=bucket, Prefix=inventory_prefix, Delimiter="/"):
		for entry in page.get("CommonPrefixes", []):
			common_prefixes.append(entry["Prefix"])
	return common_prefixes


def main():
	parser = argparse.ArgumentParser(description="Fetch the latest PMC Cloud Service (S3) daily inventory and derive a listing of article XML keys")
	parser.add_argument("--bucket", type=str, default="pmc-oa-opendata", help="PMC Cloud Service S3 bucket name")
	parser.add_argument("--inventoryPrefix", type=str, default="inventory-reports/pmc-oa-opendata/metadata/", help="Prefix under which dated inventory cycles are stored")
	parser.add_argument("--outListing", type=str, required=True, help="Where to write the sorted, deduplicated list of s3:// XML object URIs")
	parser.add_argument("--region", type=str, default="us-east-1", help="AWS region for the S3 client")
	parser.add_argument("--endpointUrl", type=str, default=None, help="Override S3 endpoint URL (for testing against a local fake S3)")
	args = parser.parse_args()

	client = get_anonymous_s3_client(region=args.region, endpoint_url=args.endpointUrl)

	print("Finding latest PMC inventory cycle under s3://%s/%s" % (args.bucket, args.inventoryPrefix))
	common_prefixes = list_cycle_prefixes(client, args.bucket, args.inventoryPrefix)
	latest_cycle_prefix = find_latest_cycle_prefix(common_prefixes, args.inventoryPrefix)
	print("Using inventory cycle: s3://%s/%s" % (args.bucket, latest_cycle_prefix))

	manifest_key = latest_cycle_prefix + "manifest.json"
	manifest = json.loads(fetch_object_text(client, args.bucket, manifest_key))
	key_column_index, part_keys = parse_manifest(manifest)

	print("Processing %d inventory CSV parts" % len(part_keys))

	xml_keys = set()
	for i, part_key in enumerate(part_keys):
		print("Processing part %d/%d: %s" % (i + 1, len(part_keys), part_key))
		sys.stdout.flush()
		xml_keys.update(process_inventory_part(client, args.bucket, part_key, key_column_index))

	print("Found %d PMC article XML files" % len(xml_keys))

	out_dir = os.path.dirname(args.outListing)
	if out_dir:
		os.makedirs(out_dir, exist_ok=True)

	tmp_path = args.outListing + ".tmp"
	with open(tmp_path, "w") as f:
		for xml_key in sorted(xml_keys):
			f.write("s3://%s/%s\n" % (args.bucket, xml_key))
	os.replace(tmp_path, args.outListing)

	print("Output to %s complete" % args.outListing)


if __name__ == "__main__":
	main()
