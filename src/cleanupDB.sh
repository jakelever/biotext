#!/bin/bash
set -euxo pipefail

echo "Truncating DB files"
for f in $(find working_db -name '*.sqlite' -size +0 | sort )
do
	timestamp=$(date -R -r $f)
	> $f
	touch -d "$timestamp" $f
done

echo "Deleting PMC archives"
rm -f pmc_archives/*.gz

