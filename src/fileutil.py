import gzip


def open_maybe_gzip(path, mode='rb'):
	"""Open a file in binary mode, transparently gzip (de)compressing if the filename ends with .gz"""
	if path.endswith('.gz'):
		return gzip.open(path, mode)
	return open(path, mode)
