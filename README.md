# BioText

<p>
	<a href="https://github.com/jakelever/biotext/actions/workflows/tests.yml">
		<img src="https://github.com/jakelever/biotext/actions/workflows/tests.yml/badge.svg" />
	</a>
	<a href="https://opensource.org/licenses/MIT">
		<img src="https://img.shields.io/badge/License-MIT-blue.svg" />
	</a>
</p>

Sometimes you need a easily-updated local copy of PubMed and PubMed Central. This project can help with that. It manages the download of PubMed and PubMed Central and converting it into the nice BioC XML format while keeping important metadata. It also handles the update process without redoing all the previous downloading and computation.

## Advantages

- Deals with format conversion
- Batches PubMed Central (~8,000,000 article versions) into chunks that are easier to parallelise
- Uses Snakemake, so can run on a single machine or be deployed on a cluster

## Details

PubMed is released as a series of XML files with a [baseline of files and updates released daily](https://www.nlm.nih.gov/databases/download/pubmed_medline.html). Each file has tens of thousands of titles and abstracts along with metadata. Each update file may contain new documents or updates to previous documents. These files follow the [PubMed XML standard](https://www.nlm.nih.gov/bsd/licensee/data_elements_doc.html). This project converts each file into the [BioC format](http://bioc.sourceforge.net/).

PubMed Central offers full-text articles of documents in a different XML format. Since August 2026, PubMed Central distributes this content through the [PMC Cloud Service](https://pmc.ncbi.nlm.nih.gov/tools/pmcaws/), a public S3 bucket (`pmc-oa-opendata`) that replaced the old FTP bulk archives. Each article version (e.g. `PMC10009416.1`) has its own object prefix containing its XML, and a daily inventory report enumerates every article currently in the bucket. This project fetches the latest inventory, identifies article versions not yet converted, batches them (2000 documents per batch by default), and streams each batch's XML straight from S3 through the conversion into BioC XML — no bulk archive is downloaded and no raw XML is kept locally.

## Things To Be Aware Of

There are few details that you should keep at the back of your mind when using this project.

- This project does not deal with duplicates of documents, both in the PubMed update files, and documents in PubMed Central that are also in PubMed. Any text mining of these documents should do a final pass to identify the latest version of a document, i.e. going through new-to-old PubMed Central files before new-to-old PubMed files.
- PubMed Central files contain a lot of Unicode characters while PubMed generally does not. An abstract for an article that is in both resources may be processed differently in the PubMed Central file due to Unicode characters.
- Yearly releases of PubMed means that there is a yearly cleanup required. More details are in the Yearly Baseline Releases below and BioText will throw an error to try to warn you about a new release.
- PMC content is streamed directly from S3 and converted in place — there is no local mirror of raw PMC XML (unlike the old *pmc_archives* directory). *pmc_batches/batches.json* only stores small lists of S3 object keys, not article content, so re-running conversion for a batch re-fetches its XML from S3.

## Usage

There are two core steps involved shown below with single-core Snakemake calls for downloading and conversion. Suggestions for running on more cores or a cluster are further below.

```bash
# 1. Fetch the PubMed listing and the latest PMC inventory, and batch new PMC articles (lightweight, single thread)
snakemake --cores 1 downloaded.flag

# 2. Convert PubMed files and PMC batches to BioC XML (network-bound, parallelises well)
snakemake --cores 1 converted.flag
```

Step 1 writes small listing/batch manifests to *listings/* and *pmc_batches/*. Step 2 needs outbound network access to fetch PubMed (FTP) and PMC (S3) content, and writes the converted files to a *biocxml* directory as gzipped BioC XML (*.bioc.xml.gz). No bulk PMC archive is ever stored locally.

If you have uncompressed *.bioc.xml files from an older version of BioText, compress them in place with `gzip biocxml/*.bioc.xml` (and delete any old *pmids/* files) rather than regenerating them; Snakemake will refuse to run while uncompressed files remain.

### Running on more cores

Increase `--cores` to convert PubMed files and PMC batches in parallel on a single machine:

```bash
snakemake --cores 8 converted.flag
```

### Tuning PMC batch size

The `PMC_BATCH_SIZE` environment variable (default 2000) controls how many PMC articles go into each batch/job during step 1, e.g. `PMC_BATCH_SIZE=4000 snakemake --cores 1 downloaded.flag`. Smaller batches create more, shorter jobs (useful if S3 fetch latency dominates over conversion time on a single machine); larger batches create fewer, longer jobs (useful on clusters with job-submission-rate limits). Pair this with the `set-resources` values in a Snakemake profile (see below) to size each job's memory/runtime request accordingly.

### Cluster / SLURM usage

Cluster execution uses Snakemake's [executor plugins](https://snakemake.github.io/snakemake-plugin-catalog/) rather than the older `--cluster` string syntax. For SLURM:

```bash
pip install -U snakemake-executor-plugin-slurm
snakemake --profile profiles/slurm -j 200 converted.flag
```

`profiles/slurm/config.yaml` sets default and per-rule resource requests (`mem_mb`, `runtime`) and a SLURM partition — edit `slurm_partition` to match your cluster before running.

## Dependencies

This project requires Python 3.11+ with dependencies that can be installed with pip.

```bash
pip install -U snakemake bioc boto3
```

For testing, it also uses biopython and moto.

```bash
pip install -U biopython moto
```

## Yearly Baseline Releases

Every year, PubMed is given a new baseline release with daily updates based from this (typically in Nov/Dec). BioText will throw an error (below) if it sees any old baseline/update files in the biocxml/ directory. This will happen when a new baseline is released. You can see the year of the release by the first number in the filename. For example, pubmed\_updatefiles\_**20**n1478.bioc.xml.gz is from the 2020 release.

When this happens, it's time for a yearly clean-out. You should delete the old PubMed files (which will likely be all PubMed files in biocxml). You will also need to delete any downstream files based upon these files to make sure that other projects don't end up with duplicate files.

```text
AssertionError in line 66 of /projects/jlever/github/biotext/Snakefile:
Found unexpected PubMed files (e.g. biocxml/pubmed_baseline_20n0001.bioc.xml.gz) in biocxml directory. Likely due to a new PubMed baseline release. These should be manually deleted as well as downstream files. Check the project README for more details under section Yearly Baseline Releases.
  File "/projects/jlever/github/biotext/Snakefile", line 66, in <module>
```

## Contributing

Contributions are very welcome.

## License

Distributed under the terms of the [MIT](http://opensource.org/licenses/MIT) license, "BioText" is free and open source software

## Issues

If you encounter any problems, please [file an issue](https://github.com/jakelever/biotext/issues) along with a detailed description.
