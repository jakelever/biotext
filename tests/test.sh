#!/bin/bash
set -ex

if [[ -d pmc_batches || -d biocxml ]]; then
	echo "ERROR: pmc_batches or biocxml directory already exists. Cannot continue"
	exit 1
fi

# Fetch a single real PMC article to serve as fake-S3 test content
python src/fetchEUtils.py --database pmc --identifier 46506 --email jake.lever@glasgow.ac.uk --o test_article.nxml

# Start a local fake S3 server (moto), pre-populated with a fake PMC Cloud Service bucket
python tests/moto_pmc_fixture.py --articleFile test_article.nxml > moto_fixture.log 2>&1 &
MOTO_PID=$!
trap "kill $MOTO_PID 2>/dev/null || true" EXIT

for i in $(seq 30); do
	if grep -q READY moto_fixture.log 2>/dev/null; then
		break
	fi
	sleep 1
done
grep -q READY moto_fixture.log || { echo "ERROR: fake S3 fixture did not become ready"; cat moto_fixture.log; exit 1; }

rm test_article.nxml

export AWS_ACCESS_KEY_ID=testing
export AWS_SECRET_ACCESS_KEY=testing
export AWS_DEFAULT_REGION=us-east-1
export AWS_ENDPOINT_URL_S3=http://127.0.0.1:5001

# We'll get the latest PubMed listing
sh src/preparePubmed.sh

# We'll just use the last PubMed file
mkdir -p listings
tail -n 1 listings/pubmed.txt > single_file.txt
mv single_file.txt listings/pubmed.txt

# Fetch the fake PMC inventory and batch it, using the real (unmodified) pipeline
# script against the fake bucket (via AWS_ENDPOINT_URL_S3 above)
bash src/preparePMC.sh

# Then run the main convert code using Snakemake
snakemake --cores 1 converted.flag

# Cleaning up after test
kill $MOTO_PID 2>/dev/null || true
rm -fr pmc_batches biocxml listings
rm -f converted.flag downloaded.flag moto_fixture.log
