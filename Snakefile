
localrules: convert_biocxml

import os
import json

from snakemake.remote.FTP import RemoteProvider as FTPRemoteProvider
FTP = FTPRemoteProvider()





#  ____                      _                 _ 
# |  _ \  _____      ___ __ | | ___   __ _  __| |
# | | | |/ _ \ \ /\ / / '_ \| |/ _ \ / _` |/ _` |
# | |_| | (_) \ V  V /| | | | | (_) | (_| | (_| |
# |____/ \___/ \_/\_/ |_| |_|_|\___/ \__,_|\__,_|
#                                                

# Delete the flags so that those rules have to be evaluated
if os.path.isfile("downloaded.flag"):
	os.remove("downloaded.flag")

rule download:
	input: [ "preparePubmed.sh", "preparePMC.sh" ]
	output: "downloaded.flag"
	shell: "sh preparePubmed.sh && sh preparePMC.sh && touch {output}"


#   ____                          _   
#  / ___|___  _ ____   _____ _ __| |_ 
# | |   / _ \| '_ \ \ / / _ \ '__| __|
# | |__| (_) | | | \ V /  __/ |  | |_ 
#  \____\___/|_| |_|\_/ \___|_|   \__|
#                                     

if os.path.isfile("converted.flag"):
	os.remove("converted.flag")

pubmed_biocxml_files, pmc_biocxml_files = [], []

# Use the pubmed_listing file to get a list of output files for each PubMed XML file
if os.path.isfile('pubmed_listing.txt'):
	with open('pubmed_listing.txt') as f:
		pubmed_biocxml_files = []
		for line in f:
			split = line.strip('\n').split('/')
			filename = split[-1].replace('.xml.gz','').replace('pubmed','')
			dir = split[-2]
			pubmed_biocxml_files.append(f"biocxml/pubmed_{dir}_{filename}.bioc.xml")

# Use the PMC groupings file to get a list of output files
if os.path.isfile('pmc_archives/groupings.json'):
	with open('pmc_archives/groupings.json') as f:
		pmc_blocks = sorted(json.load(f)['groups'].keys())
		pmc_biocxml_files = [ f"biocxml/pmc_{b}.bioc.xml" for b in pmc_blocks ]

rule convert_biocxml:
	input: 
		pubmed = pubmed_biocxml_files,
		pmc_downloaded = 'pmc_archives/groupings.json',
		pmc = pmc_biocxml_files
	output: "converted.flag"
	shell: "touch {output}"


rule pubmed_convert_biocxml:
	output: "biocxml/pubmed_{dir}_{f}.bioc.xml"
	#shell: "python convert.py --i <(curl --silent ftp://ftp.ncbi.nlm.nih.gov/pubmed/{wildcards.dir}/pubmed{wildcards.f}.xml.gz | gunzip) --iFormat pubmedxml --o {output} --oFormat biocxml"
	shell: "python convertPubmed.py --url ftp://ftp.ncbi.nlm.nih.gov/pubmed/{wildcards.dir}/pubmed{wildcards.f}.xml.gz --o {output} --oFormat biocxml"

rule pmc_convert_biocxml:
	input: "pmc_archives"
	output: "biocxml/pmc_{block}.bioc.xml"
	shell: "python convertPMC.py --pmcDir {input} --block {wildcards.block} --format biocxml --outFile {output}"



#  ____        _   _____     _             
# |  _ \ _   _| |_|_   _|_ _| |_ ___  _ __ 
# | |_) | | | | '_ \| |/ _` | __/ _ \| '__|
# |  __/| |_| | |_) | | (_| | || (_) | |   
# |_|    \__,_|_.__/|_|\__,_|\__\___/|_|   
#                                          

if os.path.isfile("pubtator_downloaded.flag"):
	os.remove("pubtator_downloaded.flag")
if os.path.isfile("pubtator.flag"):
	os.remove("pubtator.flag")

pubtator_files = []

if os.path.isdir('biocxml'):
	pubtator_files = [ f"pubtator/{f}" for f in os.listdir('biocxml') ]

rule download_pubtator:
	output: "pubtator_downloaded.flag"
	shell: "curl -o bioconcepts2pubtatorcentral.gz ftp://ftp.ncbi.nlm.nih.gov/pub/lu/PubTatorCentral/bioconcepts2pubtatorcentral.gz && touch {output}"

rule align_with_pubtator:
	input: 
		biocxml="biocxml/{f}.bioc.xml"
	output: "pubtator/{f}.bioc.xml"
	shell: "python alignWithPubtator.py --inBioc {input.biocxml} --annotations <(zcat bioconcepts2pubtatorcentral.gz) --outBioc {output}"

rule pubtator_complete:
	input: pubtator_files
	output: "pubtator.flag"
	shell: "touch {output}"



#  ____  __  __ ___ ____      
# |  _ \|  \/  |_ _|  _ \ ___ 
# | |_) | |\/| || || | | / __|
# |  __/| |  | || || |_| \__ \
# |_|   |_|  |_|___|____/|___/
#                             

if os.path.isfile("pmids.flag"):
	os.remove("pmids.flag")

pmid_files = []
if os.path.isdir('biocxml'):
	pmid_files = [ "pmids/%s" % f.replace('.bioc.xml','.txt') for f in os.listdir('biocxml') ]

rule gather_all_pmids:
	input: pmid_files
	output: "pmids.flag"
	shell: "touch {output}"

rule gather_pmids:
	input: "biocxml/{f}.bioc.xml"
	output: "pmids/{f}.txt"
	shell: ' {{ grep -hoP "<infon key=.pmid.>\d+</infon>" {input} || true; }} | tr ">" "<" | cut -f 3 -d "<" | sort -u > {output}'

