#!/bin/bash
set -ex

if [[ -d pmc_archives || -d biocxml || -d working_db ]]; then
	echo "ERROR: pmc_archives, biocxml or working_db directory already exists. Cannot continue"
	exit 1
elif [[ -f biotext.sqlite ]]; then
	echo "ERROR: biotext.sqlite already exists. Cannot continue"
	exit 1
fi

mkdir pmc_archives

# Copy over the test data we'll use (which is a single PMC file in an archive)
#cp -r test_data pmc_archives

# Let's create some test data for PMC (from a single article) and tar it up
python src/fetchEUtils.py --database pmc --identifier 46506 --email jlever@stanford.edu --o pmc_test_data.nxml
tar -czf pmc_archives/pmc_example_archive.tar.gz pmc_test_data.nxml
rm pmc_test_data.nxml

# Run the grouping code on it
python src/groupPMC.py --inPMCDir pmc_archives --prevGroupings pmc_archives/groupings.json --outGroupings pmc_archives/groupings.json

# We'll get the latest PubMed listing
sh src/preparePubmed.sh

# We'll just use the last PubMed file
mkdir -p listings
tail -n 1 listings/pubmed.txt > single_file.txt
mv single_file.txt listings/pubmed.txt

# Then run the main convert code using Snakemake
snakemake --cores 1 converted.flag

# Then run the main convert code using Snakemake
snakemake --cores 1 db.flag

# Cleaning up after test
rm biotext.db
rm -fr pmc_archives biocxml working_db listings
rm -f converted.flag db.flag
