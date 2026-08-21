import argparse
import csv
import gzip
import io
import json
import time

import boto3
from moto.server import ThreadedMotoServer

BUCKET = "pmc-oa-opendata"
CYCLE = "2026-08-20T01-00Z"
INVENTORY_PREFIX = f"inventory-reports/pmc-oa-opendata/metadata/{CYCLE}/"


def populate_bucket(endpoint_url, article_file, article_key):
	client = boto3.client(
		"s3",
		endpoint_url=endpoint_url,
		region_name="us-east-1",
		aws_access_key_id="testing",
		aws_secret_access_key="testing",
	)

	client.create_bucket(Bucket=BUCKET)
	client.put_bucket_policy(Bucket=BUCKET, Policy=json.dumps({
		"Version": "2012-10-17",
		"Statement": [{
			"Effect": "Allow",
			"Principal": "*",
			"Action": "s3:GetObject",
			"Resource": f"arn:aws:s3:::{BUCKET}/*",
		}],
	}))

	with open(article_file, "rb") as f:
		article_bytes = f.read()
	xml_key = f"{article_key}/{article_key}.xml"
	client.put_object(Bucket=BUCKET, Key=xml_key, Body=article_bytes)

	# One inventory row pointing at a JSON metadata object we never actually
	# create, since fetchPMCInventory.py only ever derives the XML key from
	# the CSV row and doesn't fetch the metadata JSON itself.
	csv_buffer = io.StringIO()
	csv.writer(csv_buffer).writerow([BUCKET, f"metadata/{article_key}.json", "2026-08-19T00:00:00.000Z", "fakeetag"])
	gz_buffer = io.BytesIO()
	with gzip.GzipFile(fileobj=gz_buffer, mode="wb") as gz:
		gz.write(csv_buffer.getvalue().encode("utf-8"))
	gz_bytes = gz_buffer.getvalue()

	part_key = INVENTORY_PREFIX + "data/part0.csv.gz"
	client.put_object(Bucket=BUCKET, Key=part_key, Body=gz_bytes)

	manifest = {
		"sourceBucket": BUCKET,
		"fileSchema": "Bucket, Key, LastModifiedDate, ETag",
		"files": [{"key": part_key, "size": len(gz_bytes), "MD5checksum": ""}],
	}
	client.put_object(Bucket=BUCKET, Key=INVENTORY_PREFIX + "manifest.json", Body=json.dumps(manifest).encode("utf-8"))


def main():
	parser = argparse.ArgumentParser(description="Run a local moto S3 server pre-populated with a fake PMC Cloud Service bucket, for use as a test fixture")
	parser.add_argument("--port", type=int, default=5001)
	parser.add_argument("--articleFile", required=True, type=str, help="A real PMC article XML file to serve as the fake bucket's test content")
	parser.add_argument("--articleKey", default="PMC_TEST.1", type=str, help="Fake article-version identifier to use")
	args = parser.parse_args()

	server = ThreadedMotoServer(port=args.port)
	server.start()

	populate_bucket(f"http://127.0.0.1:{args.port}", args.articleFile, args.articleKey)

	print("READY", flush=True)

	try:
		while True:
			time.sleep(3600)
	except KeyboardInterrupt:
		pass
	finally:
		server.stop()


if __name__ == "__main__":
	main()
