
import os
import json

from snakemake.remote.FTP import RemoteProvider as FTPRemoteProvider
FTP = FTPRemoteProvider()

pubmed_biocxml_file, pmc_biocxml_files = [], []

# Use the pubmed_listing file to get a list of output files for each PubMed XML file
if os.path.isfile('pubmed_listing.txt'):
	with open('pubmed_listing.txt') as f:
		pubmed_biocxml_files = []
		for line in f:
			split = line.strip('\n').split('/')
			filename = split[-1].replace('.xml.gz','').replace('pubmed','')
			dir = split[-2]
			pubmed_biocxml_file = "biocxml/pubmed_%s_%s.bioc.xml" % (dir,filename)
			pubmed_biocxml_files.append(pubmed_biocxml_file)

# Use the PMC groupings file to get a list of output files
if os.path.isfile('pmc_archives/groupings.json'):
	with open('pmc_archives/groupings.json') as f:
		pmc_blocks = sorted(json.load(f)['groups'].keys())
		pmc_biocxml_files = [ "biocxml/pmc_%s.bioc.xml" % b for b in pmc_blocks ]

rule convert_biocxml:
	input: 
		pubmed = pubmed_biocxml_files,
		pmc_downloaded = 'pmc_archives/groupings.json',
		pmc = pmc_biocxml_files
	output: "converted_biocxml.flag"
	shell: "touch -d '10 years ago' {output}"

rule download:
	input: "downloadAndPrepare.sh"
	output: "downloaded.flag"
	shell: "sh downloadAndPrepare.sh && touch -d '10 years ago' {output}"

rule pubmed_convert_biocxml:
	output: "biocxml/pubmed_{dir}_{f}.bioc.xml"
	#shell: "python convert.py --i <(curl --silent ftp://ftp.ncbi.nlm.nih.gov/pubmed/{wildcards.dir}/pubmed{wildcards.f}.xml.gz | gunzip) --iFormat pubmedxml --o {output} --oFormat biocxml"
	shell: "python convertPubmed.py --url ftp://ftp.ncbi.nlm.nih.gov/pubmed/{wildcards.dir}/pubmed{wildcards.f}.xml.gz --o {output} --oFormat biocxml"

rule pmc_convert_biocxml:
	input: "pmc_archives"
	output: "biocxml/pmc_{block}.bioc.xml"
	shell: "python convertPMC.py --pmcDir {input} --block {wildcards.block} --format biocxml --outFile {output}"

