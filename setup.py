from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path


here = path.abspath(path.dirname(__file__))


with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='nwbn-conversion-tools',
    version='0.1',
    description='Convert data to nwb',
    long_description=long_description,
    author='Ben Dichter and Luiz Tauffer',
    author_email='ben.dichter@gmail.com',
    keywords='nwb',
    packages=find_packages(),
    install_requires=['pynwb', 'tqdm', 'natsort', 'numpy', 'scipy', 'bs4',
        'pandas', 'jupyter', 'matplotlib', 'h5py', 'pyyaml',
        'spikeextractors', 'spikesorters', 'spiketoolkit', 'herdingspikes',
        'PySide2', 'nwbwidgets'])
