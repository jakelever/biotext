#!/bin/bash
#
#SBATCH --job-name=biotext_update
#
#SBATCH --time=24:00:00
#SBATCH -p rbaltman
#SBATCH --mem=4G

#clusterFlags="--cores 1"
set -ex

clusterFlags="-j 100 --cluster ' mysbatch -p rbaltman --mem 8G' --latency-wait 60"

rm -f downloaded.flag converted_biocxml.flag

snakemake -j 100 --cluster ' mysbatch -p rbaltman --mem 8G' --latency-wait 60 --nolock downloaded.flag

snakemake -j 100 --cluster ' mysbatch -p rbaltman --mem 8G' --latency-wait 60 --nolock converted_biocxml.flag

