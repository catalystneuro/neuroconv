from setuptools import setup, find_packages
import subprocess
# To use a consistent encoding
from codecs import open
from os import path


here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md')) as f:
    long_description = f.read()

# Get requirements
with open(path.join(here, 'requirements-test.txt')) as f:
    install_requires = f.read().strip().split('\n')

# Get remote version
remote_version = (
    subprocess.run(["git", "describe", "--tags"], stdout=subprocess.PIPE)
    .stdout.decode("utf-8")
    .strip()
)
assert "." in remote_version

setup(
    name='nwb-conversion-tools',
    version=remote_version,
    description='Convert data to nwb',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Ben Dichter and Luiz Tauffer',
    author_email='ben.dichter@gmail.com',
    url='https://github.com/catalystneuro/nwb-conversion-tools',
    keywords='nwb',
    packages=find_packages(),
    package_data={"": ['template_metafile.yml']},
    include_package_data=True,
    python_requires=">=3.7",
    install_requires=install_requires,
    entry_points={
        'console_scripts': ['nwb-gui=nwb_conversion_tools.gui.command_line:main'],
    }
)
