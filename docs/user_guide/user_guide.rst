User Guide
==========

NeuroConv allows you to easily build programs to convert data from neurophysiology experiments
to NWB. The building-blocks of these conversions are ``DataInterface`` classes. Each
``DataInterface`` is responsible for a specific format of data, and contains methods to
read data and metadata from that format and write it to NWB. We have pre-built ``DataInterface``
classes for many common data formats available in our :ref:`Conversion Gallery <conversion_gallery>`.

NWB files often combine data from multiple sources- neurophysiology raw and processed data,
behavior video and extracted position, stimuli, etc. A full conversion can require handling all
of these different data types at the same time. The ``NWBConverter`` class allows you to combine
multiple ``DataInterface`` objects into a single conversion, and provides methods to aggregate
and synchronize data across multiple sources.

.. toctree::
  :maxdepth: 2

  datainterfaces
  nwbconverter
  yaml
  schemas
