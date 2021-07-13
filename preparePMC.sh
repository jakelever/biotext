#!/bin/bash
set -euxo pipefail

mkdir -p listings
rm -f listings/pmc.txt

echo "Updating PubMed Central (Open Access / Author Manuscript) listings"

for ftpPath in "ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_bulk/" "ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/manuscript/"
do
	curl --silent $ftpPath |\
	grep -oP "\S+.xml.tar.gz" |\
	sort -u |\
	awk -v ftpPath=$ftpPath ' { print ftpPath$0 } ' > tmp_listing.txt

	listing_count=`cat tmp_listing.txt | wc -l`
	if [ $listing_count -eq 0 ]; then
		echo "ERROR: Didn't find any PMC files at path: $ftpPath"
		exit 1
	fi

	cat tmp_listing.txt >> listings/pmc.txt
	rm tmp_listing.txt
done

echo "Downloading PubMed Central archives"

mkdir -p pmc_archives
cd pmc_archives

rm -f download.tmp.gz

while read ftpPath
do
	f=`echo $ftpPath | grep -oP "[^/]+$"`

	timestamp="Wed, 31 Dec 1969 16:00:00 -0800"
	if [ -f $f ]; then
		timestamp=`date -R -d @$(stat -c '%Y' $f)`
	fi

	
	DOWNLOAD_SUCCESS=0
	for retry in $(seq 10)
	do
		RETVAL=0
		curl -o download.tmp.gz $ftpPath --time-cond "$timestamp" || {
			RETVAL=$?
			true
		}

		if [ $RETVAL -ne 0 ]; then
			echo "ERROR with curl. Retrying..."
			continue
		fi

		if ! gzip -t download.tmp.gz; then
			echo "ERROR with archive integrity. Retrying..."
			continue
		fi

		DOWNLOAD_SUCCESS=1
		break
	done

	if [ $DOWNLOAD_SUCCESS -eq 0 ]; then
		echo "ERROR: Retried too many time to download $ftpPath"
		exit 1
	fi

	if [ -f download.tmp.gz ]; then
		mv download.tmp.gz $f
	fi

done < ../listings/pmc.txt

echo "Running grouping on PubMed Central data"

python ../groupPMC.py --inPMCDir . --prevGroupings groupings.json.prev --outGroupings groupings.json

cp groupings.json groupings.json.prev

