# BioConverters Package

![PyPi](https://img.shields.io/pypi/v/bioconverters.svg) ![build](https://github.com/jakelever/bioconverters/workflows/build/badge.svg?branch=master) [![codecov](https://codecov.io/gh/jakelever/bioconverters/branch/master/graph/badge.svg)](https://codecov.io/gh/jakelever/bioconverters)

The bioconverters packages contains functions for converting PubMed and PMC style XML into BioC format.

## Getting Started

Install with pip

```bash
pip install bioconverters
```

Now you are ready to start converting files. Assuming you already have a file containing PMC formatted XML

```python
from bioconverters import pubmedxml2bioc

for doc in pubmedxml2bioc('/path/to/pmc/xml/file.xml'):
    # do stuff with bioc doc
```

## Customizing Handlers

You can overload the parse functions that deal with specific tags but providing the handlers argument. In the example below we are writing a parser for an element which we are omitting from the final text content.

```python
from bioconverters.util import TextChunk
from bioconverters import pubmedxml2bioc

def ignore_element(xml_element, custom_handlers):
    tail = (elem.tail or "").strip()
    return [TextChunk(tail, elem)]


for doc in pubmedxml2bioc('/path/to/pmc/xml/file.xml', tag_handlers={'table': ignore_element}):
    # do stuff with bioc doc
```

## Trim Sentences

You can also choose to truncate sentences to a maximum length. This is on by default. To turn this option off use the flag

```python
for doc in pubmedxml2bioc('/path/to/pmc/xml/file.xml', trim_sentences=False):
    # do stuff with bioc doc
```

## Add XML structure Information

To keep track of approximately where in the XML heirarchy a passage was derived from use the `xml_path_infon` option.

```python
for doc in pubmedxml2bioc('/path/to/pmc/xml/file.xml', xml_path_infon=False):
    # do stuff with bioc doc
```

This will add an infon to each passage (where possible) which resembles the following

```xml
<infon key="xml_path">body/sec/p</infon>
```
