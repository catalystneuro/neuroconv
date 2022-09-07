DataInterfaces
==============

The :py:class:`.BaseDataInterface` class provides a unified API for converting
data from any single input stream. See the
:ref:`Conversion Gallery <conversion_gallery>` for existing ``DataInterface``
classes and example usage. The standard workflow for using a ``DataInterface``
is as follows:

1. Installation
~~~~~~~~~~~~~~~
Each ``DataInterface`` may have custom dependencies for reading that specific
file format. To ensure that you have all the appropriate dependencies, you can
install NeuroConv in this specific configuration using pip extra requirements.
For instance, to install the dependencies for SpikeGLX, run:

.. code-block::

    pip install neuroconv[spikeglx]

2. Construction
~~~~~~~~~~~~~~~
Initialize a class and direct it to the appropriate source data. This will open
the files and read header information, setting up the system for conversion,
but generally will not read the underlying data.

.. code-block:: python

    from neuroconv.datainterfaces import SpikeGLXRecordingInterface

    spikeglx_interface = SpikeGLXRecordingInterface(file_path="path/to/towersTask_g0_t0.imec0.ap.bin")

.. note::

     To get the form of source_data, run :meth:`.BaseDataInterface.get_source_schema`,
     which returns the :ref:`source schema <source_schema>` as a JSON-schema-like dictionary informing
     the user of the required and optional input arguments to the downstream readers.


3. Get metadata
~~~~~~~~~~~~~~~
Each ``DataInterface`` can extract relevant metadata from the source files and
organize it for writing to NWB in a hierarchical dictionary. This dictionary
can be edited to include data not available in the source files.

.. code-block:: python

    metadata = spikeglx_interface.get_metadata()
    metadata["experimenter"] = ["Darwin, Charles"]


4. Run conversion
~~~~~~~~~~~~~~~~~
The ``.run_conversion`` method takes the (edited) metadata dictionary and
the path of an NWB file, and launches the actual data conversion into NWB.
This process generally reads and writes large datasets piece-by-piece, so you
can convert large datasets without overloading the computer's available RAM.
It also uses good defaults for data chunking and lossless compression, reducing
the file size of the output NWB file.

.. code-block:: python

    spikeglx_interface.run_conversion(
        save_path="path/to/destination.nwb",
        metadata=metadata
    )
