#!/bin/bash
set -ex

mkdir -p listings

rm -f listings/pubmed.txt

echo "Updating PubMed Listing"

for dir in "baseline" "updatefiles"
do
	ftpPath=ftp://ftp.ncbi.nlm.nih.gov/pubmed/$dir/

	curl --silent $ftpPath |\
	grep -oP "pubmed\w+.xml.gz" |\
	sort -u |\
	awk -v ftpPath=$ftpPath ' { print ftpPath$0 } ' >> listings/pubmed.txt
done

