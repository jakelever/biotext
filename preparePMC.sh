#!/bin/bash
set -ex

rm -f pmc_listing.txt

echo "Updating PubMed Central (Open Access / Author Manuscript) listings"

for ftpPath in "ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_bulk/" "ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/manuscript/"
do
	curl --silent $ftpPath |\
	grep -oP "\S+.xml.tar.gz" |\
	sort -u |\
	awk -v ftpPath=$ftpPath ' { print ftpPath$0 } ' >> pmc_listing.txt
done

echo "Downloading PubMed Central archives"

mkdir -p pmc_archives
cd pmc_archives

rm -f download.tmp

while read ftpPath
do
	f=`echo $ftpPath | grep -oP "[^/]+$"`

	timestamp="Wed, 31 Dec 1969 16:00:00 -0800"
	if [ -f $f ]; then
		timestamp=`date -R -d @$(stat -c '%Y' $f)`
	fi

	curl -o download.tmp $ftpPath --time-cond "$timestamp"
	if [ -f download.tmp ]; then
		mv download.tmp $f
	fi

done < ../pmc_listing.txt

echo "Running grouping on PubMed Central data"

python ../groupPMC.py --inPMCDir . --prevGroupings groupings.json.prev --outGroupings groupings.json

cp groupings.json groupings.json.prev

