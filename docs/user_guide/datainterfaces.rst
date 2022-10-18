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

.. note::

     If you are using `zsh` for command interpreter, you will have to quote the
     argument like this:

     .. code-block::

         pip install 'neuroconv[spikeglx]'

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


3.1. Load metadata from YAML
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
This metadata can also be stored in a YAML file.

For guidance on metadata format check out the recommended
:nwbinspector:`Best Practices for file metadata <best_practices/nwbfile_metadata.html#file-metadata>`.

.. code-block:: yaml

    NWBFile:
      related_publications: 'doi: ### or https://doi.org/### or an APA/MLA citation of the publication'
      session_description: >
        A rich text description of the experiment. Can also just be the abstract of the publication.
      institution: My Institution
      lab: My Lab
      experimenter:
        - Last, First Middle
        - Last, First Middle
    Subject:
      species: Rattus norvegicus

For a complete view on NWBFile metadata check out the API documentation for :py:class:`~pynwb.file.NWBFile`
and :py:class:`~pynwb.file.Subject` for Subject metadata.

The content of the YAML file can be loaded as a dictionary using a utility method
:py:meth:`~neuroconv.utils.dict.load_dict_from_file`.

The metadata that is automatically fetched from the source data can be updated
using the :py:meth:`~neuroconv.utils.dict.dict_deep_update` method with your metadata.

.. code-block:: python

    from neuroconv.utils.dict import load_dict_from_file, dict_deep_update

    metadata_path = "my_lab_metadata.yml"
    metadata_from_yaml = load_dict_from_file(file_path=metadata_path)

    metadata = spikeglx_interface.get_metadata()
    metadata = dict_deep_update(metadata, metadata_from_yaml)

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
