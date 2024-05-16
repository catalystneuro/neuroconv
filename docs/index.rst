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

* Reads data from 42 popular neurophysiology data formats and writes to NWB using best practices.
* Extracts relevant metadata from each format.
* Handles large data volume by reading datasets piece-wise.
* Minimizes the size of the NWB files by automatically applying chunking and lossless compression.
* Supports ensembles of multiple data streams, and supports common methods for temporal alignment of streams.



How to use the documentation
----------------------------

Our documentation is structured to cater to users ranging from beginners to advanced developers and contributors.
Below is an overview of the key sections to help you navigate our documentation effectively

* **Getting Started: Conversion Examples Gallery**

  If you're new to NeuroConv or NWB, start with the :ref:`Conversion Examples Gallery <conversion_gallery>`.
  This section provides concise scripts for converting data from common formats (e.g., Blackrock, Plexon, Neuralynx) to NWB. It's designed to get you up and running quickly.

* **User Guide**

  The :ref:`User Guide <user_guide>` offers a comprehensive overview of NeuroConv's data model and functionalities.
  It is recommended for users who wish to understand the underlying concepts and extend their scripts beyond basic conversions.

* **Catalogue of Projects**

  :ref:`The Catalogue of Neuroconv Projects <catalogue>` section showcases a collection of successful conversion projects utilizing NeuroConv.
  It serves as both inspiration and a practical reference for what can be achieved with our library.

* **Developer Guide**

  For developers interested in contributing to NeuroConv, the :ref:`Developer Guide <developer_guide>` provides essential information such as
  instructions for building your own classes,  our coding style, instructions on how to build the documentation,
  run the testing suite, etc.

* **API Reference**

  Detailed documentation of the NeuroConv API can be found in the :ref:`API <api>` section.


Do you find that some information is missing or some section lacking or unclear? Reach out with an issue or pull request on our `GitHub repository <https://github.com/catalystneuro/neuroconv>`_.
We are happy to help and appreciate your feedback.

.. toctree::
  :maxdepth: 2
  :hidden:

  user_guide/index
  conversion_examples_gallery/index
  catalogue/index
  developer_guide/index
  api/index


Related links
-------------


For an overview of the NWB standard and ecocsystem, please view:

- The `NWB Overview <https://nwb-overview.readthedocs.io/en/latest/>`_

For a no code solution to conversion to NWB, please view:

- The `NWB-Guide Project <https://nwb-guide.readthedocs.io/en/latest/>`_

For more information regarding the NWB Standard, please view

- The `NWB Format Specification <https://nwb-schema.readthedocs.io/en/latest/>`_

.. seealso::

  Watch a video introduction to NeuroConv `here <https://youtu.be/QofVU-59Dd4>`_

.. Indices and tables
.. ==================
..
.. * :ref:`genindex`
.. * :ref:`modindex`
.. * :ref:`search`
