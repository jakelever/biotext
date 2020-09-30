# BioText

<p>
	<a href="https://travis-ci.org/jakelever/biotext">
		<img src="https://travis-ci.org/jakelever/biotext.svg?branch=master" />
	</a>
	<a href="https://opensource.org/licenses/MIT">
		<img src="https://img.shields.io/badge/License-MIT-blue.svg" />
	</a>
</p>

Sometimes you need a easily-updated local copy of PubMed and PubMed Central, and this project can help with that. It manages the download the PubMed and PubMed Central and converting it into the nice BioC XML format while keeping important metadata. And then it handles the update process without redoing all the previous downloading and computation.

## Advantages
- Deals with format conversion
- Chunks PubMed Central (which is normally ~2,000,000 files) into larger files that are easier to parallelise
- Uses Snakemake, so can be deployed on a cluster

## Details

PubMed is released as a series of XML files with a [baseline of files and updates released daily](https://www.nlm.nih.gov/databases/download/pubmed_medline.html). Each file has tens of thousands of titles and abstracts along with metadata. Each update file may contain new documents or updates to previous documents. These files follow the [PubMed XML standard](https://www.nlm.nih.gov/bsd/licensee/data_elements_doc.html). This project converts each file into the [BioC format](http://bioc.sourceforge.net/).

PubMed Central offers full-text articles of documents in a different XML format. A portion of PubMed Central is released for text mining as the [non-commercial and commercial licensed PubMed Central Open Access subset](https://www.ncbi.nlm.nih.gov/pmc/tools/openftlist/) and the [Author Manuscript Collection](https://www.ncbi.nlm.nih.gov/pmc/about/mscollection/). PubMed Central is released as about 15 archives of XML files. Each archive has a very large number of files which makes it somewhat unwieldy. Each new version of these archives contains a mix of new files and old files which need to be distinguished. This project identifies unprocessed files, groups them into chunk (of 2000 documents by default) and converts them to BioC XML.

**N.B.** This project does not deal with duplicates of documents, both in the PubMed update files, and documents in PubMed Central that are also in PubMed. Any text mining of these documents should do a final pass to identify the latest version of a document, i.e. going through new-to-old PubMed Central files before new-to-old PubMed files.

## Usage

There are two steps involved.

```
# 1. Downloading and grouping PubMed Central (which is a single thread)
snakemake downloaded.flag

# 2. Converting PubMed files and PubMed Central groups of files (which can be parallelised).
snakemake converted_biocxml.flag
```

Those steps will download PubMed Central to a *pmc_archives* directory and create a *biocxml* directory with the converted files.

Those calls to snakemake can then be augmented to use a cluster (or whatever local set up you have), e.g.
```
# Run a hundred jobs at a time on a SLURM cluster using sbatch
snakemake -j 100 --cluster ' sbatch' --latency-wait 60 converted_biocxml.flag
```

## Dependencies

This project requires Python 3 with dependencies that can be installed with pip.

```
pip install -U snakemake bioc ftputil
```

For testing, it also uses biopython.
```
pip install -U biopython
```

