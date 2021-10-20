from setuptools import setup

long_description = ''

with open('docs/BioConverters.md', 'r') as fh:
    long_description = fh.read()


DEV_REQS = ['black', 'flake8', 'isort', 'mypy']
TEST_REQS = ['biopython', 'snakemake', 'ftputil', 'requests', 'pytest', 'pytest-cov']

setup(
    name='bioconverters',
    version='1.0.0',
    packages=['bioconverters'],
    package_dir={'': 'src'},
    description='Convert between NCBI pubmed/PMC and BIOC formats',
    long_description=long_description,
    long_description_format='md',
    install_requires=['bioc >=1.3, <2', 'typing_extensions'],
    extras_require={'dev': DEV_REQS + TEST_REQS, 'test': TEST_REQS},
    python_requires='>=3.6',
    author='Jake Lever',
    author_email='jlever@stanford.edu',
    maintainer='Jake Lever',
    maintainer_email='jlever@stanford.edu',
)
