User Guide
==========================

NWB files often combine data from multiple sources- neurophysiology raw and processed data,
behavior video and extracted position, stimuli, etc.
A full conversion means handling all of these different data types at the same time,
and it can get tricky to ensure that timing is synchronized across different
acquisition systems. While the automated proprietary format conversions build upon
PyNWB to solve the challenges of variety of data formats and size of data,
NeuroConv build upon these automated conversion tools to provide a
system for combining data across multiple streams.

Any conversion task requires three sets of information:

#. **Source data**: The paths to existing proprietary files and directories
#. **Metadata**: The metadata that can be fetched from source data or added manually
#. **Conversion options**: The configuration to run conversion

NeuroConv relies on two tiers of structure, **DataInterfaces** and **Converters**,
to accomplish the conversion.

Users can use `graphical user interface (GUI) forms <https://github.com/catalystneuro/nwb-web-gui>`_
to interact with **DataInterfaces** and **Converters** by editing the metadata and conversion options.

.. image:: img/converter-gui-operations.png
   :align: center
   :width: 80%

Users can also use the command line interface, see examples for creating your own
Python code to run conversion in the :ref:`conversion gallery <conversion_gallery>`.

DataInterfaces and Converters
-----------------------------

**DataInterfaces** are classes that interface specific data types with NWB.
DataInterfaces are the specialist building blocks of any conversion task.
**Converters** are classes responsible for combining and coordinating the operations of
multiple DataInterfaces in order to assemble the output of complex neurophysiology
experiments into a single, time-aligned NWB file.

**DataInterface** and **Converter** classes inherit from the two main classes in the package:
:class:`.BaseDataInterface` and :class:`~.nwbconverter.NWBConverter`.

BaseDataInterface
^^^^^^^^^^^^^^^^^

:class:`.BaseDataInterface` is a unified API for converting data from
any single input stream. There are corresponding DataInterface objects for
each ``SpikeExtractor`` and ``RoiExtractor``, and additional ``DataInterface`` objects
for other types of data not supported by these packages, like videos for behavior monitoring.

``SpikeExtractor`` and ``RoiExtractor`` data readers can miss key metadata that should
go into the NWB file. DataInterface objects solve this by each providing a
:meth:`~.BaseDataInterface.get_metadata` method that inspect the source files
and pulls out any additional metadata into a JSON-like dictionary-of-dictionaries.
This metadata object can then be passed into :meth:`~.BaseDataInterface.run_conversion`,
which will write the metadata in the appropriate places in the NWB file along with
the data from the interfaces.

Here is an example of how to use a DataInterface::

    from neuroconv import SpikeGLXRecordingInterface

    source_data = dict(file_path="path/to/towersTask_g0_t0.imec0.ap.bin")

    spike_glx_recording_interface = SpikeGLXRecordingInterface(source_data)

    metadata = spike_glx_recording_interface.get_metadata()

    spike_glx_recording_interface.run_conversion(
        save_path="path/to/destination.nwb",
        metadata=metadata
    )

.. note::

     To get the form of source_data, run :meth:`.BaseDataInterface.get_source_schema`,
     which returns the :ref:`source schema <source_schema>` as a JSON-schema-like dictionary informing
     the user of the required and optional input arguments to the downstream readers.

The :ref:`metadata schema <metadata_schema>` maps certain pieces of
metadata to specific places in the NWB file. The form of this dictionary is defined
by a JSON-schema that you can get with :meth:`.BaseDataInterface.get_metadata_schema()`.


``DataInterface`` objects serve as building blocks for the :class:`.NWBConverter`,
which orchestrates a conversion that integrates data across multiple interfaces.

NWBConverter
^^^^^^^^^^^^

In neurophysiology, it is common to use multiple different acquisition or
preprocessing systems with different proprietary formats in the same session.
For instance, in a given extracellular electrophysiology experiment, you might
have raw and processed data. The NWBConverter class streamlines this
conversion process. This single NWBConversion object is responsible for
combining those multiple read/write operations. An example of how to define
a ``NWBConverter`` would be::

    from neuroconv import (
        NWBConverter,
        BlackrockRecordingExtractorInterface,
        PhySortingInterface
    )

    class ExampleNWBConverter(NWBConverter):
        data_interface_classes = dict(
            BlackrockRecording=BlackrockRecordingExtractorInterface,
            PhySorting=PhySortingInterface
        )

:py:class:`.NWBConverter` classes define a :py:attr:`.data_interface_classes` dictionary, a class
attribute that specifies all of the ``DataInterface`` classes used by this
converter. Then you just need to input ``source_data``, which specifies the
input data to each ``DataInterface``. The keys to this dictionary are arbitrary,
but must match between ``data_interface_classes`` and the ``source_data``::

    source_data = dict(
        BlackrockRecording=dict(
            file_path="raw_dataset_path"
        ),
        PhySorting=dict(
            folder_path="sorted_dataset_path"
        )
    )

    example_nwb_converter = ExampleNWBConverter(source_data)

This creates an ``NWBConverter`` object that can aggregate and distribute across
the data interfaces. To fetch metadata across all of the interfaces and merge
them together, call::

    metadata = converter.get_metadata()

The metadata can then be manually modified with any additional user-input::

    metadata["NWBFile"]["session_description"] = "NeuroConv tutorial."
    metadata["NWBFile"]["experimenter"] = "My name"
    metadata["Subject"]["subject_id"] ="ID of experimental subject"

The final metadata dictionary should follow the form defined by
``converter.get_metadata_schema()``. Now run the entire conversion with::

    converter.run_conversion(metadata=metadata, nwbfile_path="my_nwbfile.nwb")

Though this example was only for two data streams (recording and spike-sorted
data), it can easily extend to any number of sources, including video of a
subject, extracted position estimates, stimuli, or any other data source.

The sections below describe source schema and metadata schema in more detail through
another example for two data streams (ophys and ecephys data).

.. _source_schema:

Source Schema and Data
----------------------

The source schema is a JSON schema that defines the rules for organizing the source data.
DataInterface classes have the abstract method :meth:`.BaseDataInterface.get_source_schema`,
which is responsible to return the source schema in form of a dictionary.

For instance, a hypothetical ``EcephysDataInterface``, dealing with extracellular
electrophysiology data, would return the source schema as follows:

.. code-block:: json

    {
      "$schema": "http://json-schema.org/draft-07/schema#",
      "$id": "source.schema.json",
      "title": "Source data",
      "description": "Schema for the source data",
      "version": "0.1.0",
      "type": "object",
      "additionalProperties": false,
      "required": [
         "path_file_raw_ecephys",
         "path_dir_processed_ecephys"
      ],
      "properties": {
         "path_file_raw_ecephys": {
            "type": "string",
            "format": "file",
            "description": "path to raw ecephys data file"
        },
         "path_dir_processed_ecephys": {
            "type": "string",
            "format": "directory",
            "description": "path to directory containing processed ecephys data files"
        }
      }
    }

A hypothetical ``OphysDataInterface`` class would return a similar dictionary,
with properties related to optophysiology source data.
Now any lab that has simultaneous ecephys and ophys recordings that could be
interfaced with those classes can combine them using a converter.
This hypothetical ``LabConverter`` is then responsible for combining ``EcephysDataInterface``
and ``OphysDataInterface`` operations and its ``get_source_schema()`` method would return:

.. code-block:: json

    {
      "$schema": "http://json-schema.org/draft-07/schema#",
      "$id": "source.schema.json",
      "title": "Source data",
      "description": "Schema for the source data",
      "version": "0.1.0",
      "type": "object",
      "additionalProperties": false,
      "required": [
         "path_file_raw_ecephys",
         "path_dir_processed_ecephys",
         "path_file_raw_ophys",
         "path_dir_processed_ophys"
      ],
      "properties": {
         "path_file_raw_ecephys": {
            "type": "string",
            "format": "file",
            "description": "path to raw ecephys data file"
          },
         "path_dir_processed_ecephys": {
            "type": "string",
            "format": "directory",
            "description": "path to directory containing processed ecephys data files"
          },
         "path_file_raw_ophys": {
            "type": "string",
            "format": "file",
            "description": "path to raw ophys data file"
          },
          "path_dir_processed_ophys": {
             "type": "string",
             "format": "directory",
             "description": "path to directory containing processed ophys data files"
          }
        }
    }

The source schema for ``LabConverter`` therefore defines all the source fields and how they
should be filled for a conversion task from this specific ecephys/ophys experiment to an
NWB file.

.. _metadata_schema:

Metadata Schema and Data
------------------------

The metadata schema is a JSON schema that defines the rules for organizing the metadata.
The metadata properties map to the NWB classes necessary for any specific conversion task.
Similar to input data, each ``DataInterface`` produces its own metadata schema reflecting
the specificities of the dataset it interfaces with.
The ``DataInterface`` specific metadata schema can be obtained via method ``get_metadata_schema()``.
For example, the ``EcephysDataInterface`` could return a metadata schema similar to this:

.. code-block:: json

    {
      "$schema": "http://json-schema.org/draft-07/schema#",
      "$id": "metafile.schema.json",
      "title": "Metadata",
      "description": "Schema for the metadata",
      "version": "0.1.0",
      "type": "object",
      "required": ["NWBFile"],
      "additionalProperties": false,
      "properties": {
        "NWBFile": {
          "type": "object",
          "additionalProperties": false,
          "tag": "pynwb.file.NWBFile",
          "required": ["session_description", "identifier", "session_start_time"],
          "properties": {
            "session_description": {
              "type": "string",
              "format": "long",
              "description": "a description of the session where this data was generated"
            },
            "identifier": {
              "type": "string",
              "description": "a unique text identifier for the file"
            },
            "session_start_time": {
              "type": "string",
              "description": "the start date and time of the recording session",
              "format": "date-time"
            }
          }
        },
        "Ecephys": {
          "type": "object",
          "title": "Ecephys",
          "required": [],
          "properties": {
            "Device": {"$ref": "#/definitions/Device"},
            "ElectricalSeries_raw": {"$ref": "#/definitions/ElectricalSeries"},
            "ElectricalSeries_processed": {"$ref": "#/definitions/ElectricalSeries"},
            "ElectrodeGroup": {"$ref": "#/definitions/ElectrodeGroup"}
          }
        }
      }
    }

Each DataInterface also provides a way to automatically fetch as much metadata as possible
directly from the dataset it interfaces with. This is done with the method ``get_metadata()``.

``OphysDataInterface`` would return a similar dictionaries for metadata_schema and metadata,
with properties related to optophysiology data. The ``LabConverter`` will combine the
DataInterfaces specific schemas and metadatas into a full dictionaries, and potentially
include properties that lie outside the scope of specific DataInterfaces.

.. seealso::
   We have :ref:`tutorials <tutorials>` that demonstrate how to setup a conversion
   pipeline using NeuroConv.
