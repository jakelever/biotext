import sys
import time

import boto3
from botocore import UNSIGNED
from botocore.config import Config


def get_anonymous_s3_client(region="us-east-1", endpoint_url=None):
	return boto3.client(
		"s3",
		region_name=region,
		endpoint_url=endpoint_url,
		config=Config(signature_version=UNSIGNED, retries={"max_attempts": 10, "mode": "adaptive"}),
	)


def fetch_object_bytes(client, bucket, key, retries=5):
	for tryno in range(retries):
		try:
			response = client.get_object(Bucket=bucket, Key=key)
			return response["Body"].read()
		except Exception:
			print("Unexpected error (%s %s) on try %d/%d while fetching s3://%s/%s" % (sys.exc_info()[0], sys.exc_info()[1], tryno + 1, retries, bucket, key))
			time.sleep(5 * (tryno + 1))

	raise RuntimeError("Unable to fetch s3://%s/%s" % (bucket, key))


def fetch_object_text(client, bucket, key, retries=5):
	return fetch_object_bytes(client, bucket, key, retries=retries).decode("utf-8")
