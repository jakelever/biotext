import pytest

from fetchPMCInventory import derive_xml_key, find_latest_cycle_prefix, parse_manifest

INVENTORY_PREFIX = 'inventory-reports/pmc-oa-opendata/metadata/'


def test_derive_xml_key():
	assert derive_xml_key('metadata/PMC13283695.1.json') == 'PMC13283695.1/PMC13283695.1.xml'


def test_derive_xml_key_ignores_non_metadata_keys():
	assert derive_xml_key('other/PMC13283695.1.json') is None


def test_derive_xml_key_ignores_non_json_keys():
	assert derive_xml_key('metadata/PMC13283695.1.txt') is None


def test_find_latest_cycle_prefix_picks_max_date():
	common_prefixes = [
		INVENTORY_PREFIX + '2026-08-18T01-00Z/',
		INVENTORY_PREFIX + '2026-08-20T01-00Z/',
		INVENTORY_PREFIX + '2026-08-19T01-00Z/',
		INVENTORY_PREFIX + 'data/',
		INVENTORY_PREFIX + 'hive/',
	]
	assert find_latest_cycle_prefix(common_prefixes, INVENTORY_PREFIX) == INVENTORY_PREFIX + '2026-08-20T01-00Z/'


def test_find_latest_cycle_prefix_raises_when_none_found():
	with pytest.raises(AssertionError):
		find_latest_cycle_prefix([INVENTORY_PREFIX + 'data/'], INVENTORY_PREFIX)


def test_parse_manifest():
	manifest = {
		'fileSchema': 'Bucket, Key, LastModifiedDate, ETag',
		'files': [
			{'key': 'inventory-reports/pmc-oa-opendata/metadata/data/a.csv.gz'},
			{'key': 'inventory-reports/pmc-oa-opendata/metadata/data/b.csv.gz'},
		],
	}
	key_column_index, part_keys = parse_manifest(manifest)
	assert key_column_index == 1
	assert part_keys == [
		'inventory-reports/pmc-oa-opendata/metadata/data/a.csv.gz',
		'inventory-reports/pmc-oa-opendata/metadata/data/b.csv.gz',
	]
