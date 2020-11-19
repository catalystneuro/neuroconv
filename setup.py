from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path


here = path.abspath(path.dirname(__file__))


with open(path.join(here, 'README.md')) as f:
    long_description = f.read()

setup(
    name='nwb-conversion-tools',
    version='0.6.2',
    description='Convert data to nwb',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Ben Dichter and Luiz Tauffer',
    author_email='ben.dichter@gmail.com',
    url='https://github.com/catalystneuro/nwb-conversion-tools',
    keywords='nwb',
    packages=find_packages(),
    package_data={'': ['template_metafile.yml']},
    include_package_data=True,
    install_requires=[
        'pynwb', 'tqdm', 'natsort', 'numpy', 'scipy', 'pandas', 'h5py',
        'pyyaml', 'spikeextractors', 'spikesorters', 'spiketoolkit', 'lxml',
        'pyintan', 'jsonschema'
    ],
    entry_points={
        'console_scripts': ['nwb-gui=nwb_conversion_tools.gui.command_line:main'],
    }
)
