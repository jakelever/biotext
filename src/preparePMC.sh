#!/bin/bash
set -euxo pipefail

mkdir -p listings
rm -f listings/pmc.txt

echo "Updating PubMed Central (Open Access / Author Manuscript) listings"

#for ftpPath in "ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_bulk/" "ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/manuscript/"
for ftpPath in "ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/manuscript/xml/" "ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_bulk/oa_comm/xml/" "ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_bulk/oa_noncomm/xml/" "ftp://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_bulk/oa_other/xml/"
do
	curl --silent $ftpPath |\
	grep -oP "\S+.tar.gz" |\
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

mkdir -p pmc_archives
cd pmc_archives

rm -f download.tmp.gz
rm -f expected_files.txt found_files.txt unexpected_files.txt

echo "Checking on expected files..."
while read ftpPath
do
	f=`echo $ftpPath | grep -oP "[^/]+$"`

	if [[ "$f" == *".baseline."* ]]; then
		f="baseline.$f"
	else
		f="update.$f"
	fi
	echo $f >> expected_files.txt
done < ../listings/pmc.txt

find -name '*.gz' | sed -e 's/^\.\///' > found_files.txt
grep -vxFf expected_files.txt found_files.txt || true > unexpected_files.txt
UNEXPECTED_COUNT=$(cat unexpected_files.txt | wc -l)

if [ $UNEXPECTED_COUNT -ne 0 ]; then
	echo "ERROR: Unexpected GZ files found in PMC folder. Could there be a new baseline release? If so, old PMC files need to be deleted from biotext and downstream applications"
	echo
	echo "Example unexpected files:"
	head -n 10 unexpected_files.txt
	exit 1
fi

rm -f expected_files.txt found_files.txt unexpected_files.txt

NEW_FILES=0
while read ftpPath
do
	f=`echo $ftpPath | grep -oP "[^/]+$"`

	if [[ "$f" == *".baseline."* ]]; then
		f="baseline.$f"
	else
		f="update.$f"
	fi

	if [ -f $f ]; then
		echo "Skipping $f..."
		continue
	fi

	DOWNLOAD_SUCCESS=0
	for retry in $(seq 10)
	do
		RETVAL=0
		rm -f download.tmp.gz
		curl -o download.tmp.gz $ftpPath || {
			RETVAL=$?
			true
		}

		if [ $RETVAL -eq 0 ] && [ ! -f download.tmp.gz ]; then
			echo "No download needed"
			DOWNLOAD_SUCCESS=1
			break
		fi

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
		NEW_FILES=1
	fi

done < ../listings/pmc.txt

if [ $NEW_FILES -eq 1 ]; then
	echo "Running grouping on PubMed Central data"

	python ../src/groupPMC.py --inPMCDir . --prevGroupings groupings.json.prev --outGroupings groupings.json
	cp groupings.json groupings.json.prev
else
	echo "No new files so no grouping required."
fi

