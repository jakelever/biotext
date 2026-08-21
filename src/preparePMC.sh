#!/bin/bash
set -euxo pipefail

mkdir -p listings pmc_batches

echo "Fetching latest PubMed Central (PMC Cloud Service) inventory listing"
python src/fetchPMCInventory.py --outListing listings/pmc.txt

if [ -f pmc_batches/batches.json ]; then
	cp pmc_batches/batches.json pmc_batches/batches.json.prev
fi

echo "Batching PubMed Central articles for conversion"
python src/batchPMC.py --keysFile listings/pmc.txt \
	--prevBatches pmc_batches/batches.json.prev \
	--outBatches pmc_batches/batches.json \
	--batchSize "${PMC_BATCH_SIZE:-2000}"
