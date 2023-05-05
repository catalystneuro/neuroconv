NeuroConv
=========

.. image:: img/neuroconv_logo.png
  :width: 300

..
  :scale: 100 %
  :align: right

NeuroConv is a Python package for converting neurophysiology data in a variety
of proprietary formats to the Neurodata Without Borders (NWB) standard.

Features:

* Reads data from 40 popular neurophysiology data formats and writes to NWB using best practices.
* Extracts relevant metadata from each format.
* Handles large data volume by reading datasets piece-wise.
* Minimizes the size of the NWB files by automatically applying chunking and lossless compression.
* Supports ensembles of multiple data streams, and supports common methods for temporal alignment of streams.

.. toctree::
  :maxdepth: 2
  :caption: Contents

  user_guide/user_guide
  conversion_examples_gallery/conversion_example_gallery
  catalogue/catalogue
  developer_guide

.. toctree::
  :maxdepth: 2
  :caption: API Documentation

  NWBConverter <api/nwbconverter>
  BaseDataInterface <api/basedatainterface>
  Interfaces <api/interfaces>
  Tools <api/tools>
  Utils <api/utils>

For more information regarding the NWB Standard, please view

- The `NWB Format Specification <https://nwb-schema.readthedocs.io/en/latest/>`_

.. Indices and tables
.. ==================
..
.. * :ref:`genindex`
.. * :ref:`modindex`
.. * :ref:`search`
