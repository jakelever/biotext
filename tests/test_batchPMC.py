from batchPMC import compute_new_batches, next_batch_index


def test_compute_new_batches_basic():
	batches = compute_new_batches(already_batched=set(), all_keys=['c', 'a', 'b'], batch_size=2, start_index=1)
	assert batches == {
		'batch_000001': ['a', 'b'],
		'batch_000002': ['c'],
	}


def test_compute_new_batches_skips_already_batched():
	batches = compute_new_batches(already_batched={'a'}, all_keys=['a', 'b', 'c'], batch_size=2, start_index=3)
	assert batches == {
		'batch_000003': ['b', 'c'],
	}


def test_compute_new_batches_empty():
	assert compute_new_batches(already_batched=set(), all_keys=[], batch_size=2, start_index=1) == {}


def test_next_batch_index_empty():
	assert next_batch_index([]) == 1


def test_next_batch_index_continues_from_max():
	assert next_batch_index(['batch_000001', 'batch_000003']) == 4
