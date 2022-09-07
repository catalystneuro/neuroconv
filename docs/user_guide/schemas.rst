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