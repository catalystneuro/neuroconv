from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path


here = path.abspath(path.dirname(__file__))


with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='nwbn-conversion-tools',
    version='0.3.0',
    description='Convert data to nwb',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Ben Dichter and Luiz Tauffer',
    author_email='ben.dichter@gmail.com',
    keywords='nwb',
    packages=find_packages(),
    install_requires=[
        'pynwb', 'tqdm', 'natsort', 'numpy', 'scipy', 'bs4',
        'pandas', 'jupyter', 'matplotlib', 'h5py', 'pyyaml',
        'spikeextractors', 'spikesorters', 'spiketoolkit', 'herdingspikes',
        'PySide2', 'nwbwidgets', 'psutil', 'voila'
    ],
    entry_points = {
        'console_scripts': ['nwbn-gui=nwbn_conversion_tools.gui.command_line:main'],
    }
)
