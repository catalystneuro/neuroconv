.. _source_schema:

Defining the form of source with schemas
----------------------------------------

The ``.__init__()`` of each ``DataInterface`` has a unique call signature, requiring the source data to be input in a
specific way. Some require a ``file_path``, some a ``folder_path``, and some require additional arguments that are
necessary to read the source data properly. The same is true for the ``.run_conversion()`` methods, where some classes
have unique additional optional arguments. To communicate these requirements and options with an :py:class:`.NWBConverter` and
with interfacing software, the expected form of the input is defined using the JSON Schema language.

``DataInterface`` classes define the method
:py:func:`~neuroconv.datainterfaces.basedatainterface.BaseDataInterface.get_source_schema()`, which returns
the source schema as a JSON schema dictionary. By default, these dictionaries are automatically derived from the call signatures
and type hints of a function, and express similar information, but can also be used to define and validate inputs that are
nested dictionaries of arbitrary depth. For example, :py:func:`SpikeGLXRecordingInterface.__init__()` has the call signature

.. code-block:: python

    def __init__(
        self,
        file_path: FilePathType,
        stub_test: bool = False,
        verbose: bool = True,
    )

Calling
:py:func:`~neuroconv.datainterfaces.ecephys.spikeglx.spikeglxdatainterface.SpikeGLXRecordingInterface.get_source_schema()`
gives the following output, which is derived from the call signature and expresses identical information.

.. code-block:: json

    {
      "required": [
        "file_path"
      ],
      "properties": {
        "file_path": {
          "format": "file",
          "type": "string",
          "description": "Path to SpikeGLX file."
        },
        "stub_test": {
          "type": "boolean",
          "default": false
        },
        "verbose": {
          "type": "boolean",
          "default": true
        }
      },
      "type": "object",
      "additionalProperties": false
    }


``PhySortingInterface.get_source_schema()`` returns a similar schema:

.. code-block:: json

    {
      "required": [
        "folder_path"
      ],
      "properties": {
        "folder_path": {
          "format": "directory",
          "type": "string"
        },
        "exclude_cluster_groups": {
          "type": "array"
        },
        "verbose": {
          "type": "boolean",
          "default": true
        }
      },
      "type": "object",
      "additionalProperties": false
    }

An ``ExampleNWBConverter`` that combines these ``DataInterface`` classes will combine the JSON Schema using the keys of the
``data_interface_classes`` dictionary:

.. code-block:: python

    from neuroconv import NWBConverter,
    from neuroconv.datainterfaces import (
        SpikeGLXRecordingInterface,
        PhySortingInterface
    )

    class ExampleNWBConverter(NWBConverter):
        data_interface_classes = dict(
            SpikeGLXRecording=SpikeGLXRecordingInterface,
            PhySorting=PhySortingInterface
        )

    ExampleNWBConverter.get_source_schema()


.. code-block:: json

    {
      "$schema":"http://json-schema.org/draft-07/schema#",
      "$id":"source.schema.json",
      "title":"Source data schema",
      "description":"Schema for the source data, files and directories",
      "version":"0.1.0",
      "type":"object",
      "required":[],
      "properties":{
        "SpikeGLXRecording":{
          "required":[
            "file_path"
          ],
          "properties":{
            "file_path":{
              "format":"file",
              "type":"string",
              "description":"Path to SpikeGLX file."
            },
            "stub_test":{
              "type":"boolean",
              "default":false
            },
            "spikeextractors_backend":{
              "type":"boolean",
              "default":false
            },
            "verbose":{
              "type":"boolean",
              "default":true
            }
          },
          "type":"object",
          "additionalProperties":false
        },
        "PhySorting":{
          "required":[
            "folder_path"
          ],
          "properties":{
            "folder_path":{
              "format":"directory",
              "type":"string"
            },
            "exclude_cluster_groups":{
              "type":"array"
            },
            "verbose":{
              "type":"boolean",
              "default":true
            }
          },
          "type":"object",
          "additionalProperties":false
        }
      },
      "additionalProperties":false
    }

Conversion schemas options work similarly to source schemas.

.. _metadata_schema:

Metadata Schema
---------------

Similar to input data, each ``DataInterface`` produces its own metadata schema reflecting
the specificities of the dataset it interfaces with. The ``DataInterface``-specific metadata schema can be obtained
via the ``.get_metadata_schema()`` method. Unlike ``.get_source_schema()``, the ``DataInterface`` needs to be
initialized before calling this method.

.. code-block:: python

    fpath = f"{ECEPHY_DATA_PATH}/spikeglx/Noise4Sam_g0/Noise4Sam_g0_imec0/Noise4Sam_g0_t0.imec0.ap.bin"
    SpikeGLXRecordingInterface(file_path=fpath).get_metadata_schema()

.. code-block:: json

    {
      "required": [
        "Ecephys"
      ],
      "properties": {
        "Ecephys": {
          "required": [
            "Device",
            "ElectrodeGroup"
          ],
          "properties": {
            "Device": {
              "type": "array",
              "minItems": 1,
              "items": {
                "$ref": "#/properties/Ecephys/definitions/Device"
              }
            },
            "ElectrodeGroup": {
              "type": "array",
              "minItems": 1,
              "items": {
                "$ref": "#/properties/Ecephys/definitions/ElectrodeGroup"
              }
            },
            "Electrodes": {
              "type": "array",
              "minItems": 0,
              "renderForm": false,
              "items": {
                "$ref": "#/properties/Ecephys/definitions/Electrodes"
              }
            },
            "ElectricalSeriesRaw": {
              "required": [
                "name"
              ],
              "properties": {
                "name": {
                  "description": "The name of this TimeSeries dataset",
                  "type": "string"
                },
                "filtering": {
                  "description": "Filtering applied to all channels of the data. For example, if this ElectricalSeries represents high-pass-filtered data (also known as AP Band), then this value could be 'High-pass 4-pole Bessel filter at 500 Hz'. If this ElectricalSeries represents low-pass-filtered LFP data and the type of filter is unknown, then this value could be 'Low-pass filter at 300 Hz'. If a non-standard filter type is used, provide as much detail about the filter properties as possible.",
                  "type": "string"
                },
                "resolution": {
                  "description": "The smallest meaningful difference (in specified unit) between values in data",
                  "type": "number",
                  "default": -1
                },
                "conversion": {
                  "description": "Scalar to multiply each element in data to convert it to the specified unit",
                  "type": "number",
                  "default": 1
                },
                "starting_time": {
                  "description": "The timestamp of the first sample",
                  "type": "number"
                },
                "rate": {
                  "description": "Sampling rate in Hz",
                  "type": "number"
                },
                "comments": {
                  "description": "Human-readable comments about this TimeSeries dataset",
                  "type": "string",
                  "default": "no comments"
                },
                "description": {
                  "description": "Description of this TimeSeries dataset",
                  "type": "string",
                  "default": "no description"
                },
                "control": {
                  "description": "Numerical labels that apply to each element in data",
                  "type": "array"
                },
                "control_description": {
                  "description": "Description of each control value",
                  "type": "array"
                },
                "offset": {
                  "description": "Scalar to add to each element in the data scaled by 'conversion' to finish converting it to the specified unit.",
                  "type": "number",
                  "default": 0
                }
              },
              "type": "object",
              "additionalProperties": false,
              "tag": "pynwb.ecephys.ElectricalSeries"
            }
          },
          "type": "object",
          "additionalProperties": false,
          "tag": "Ecephys"
          },
          "definitions": {
            "Device": {
              "required": [
                "name"
              ],
              "properties": {
                "name": {
                  "description": "the name of this device",
                  "type": "string"
                },
                "description": {
                  "description": "Description of the device (e.g., model, firmware version, processing software version, etc.)",
                  "type": "string"
                },
                "manufacturer": {
                  "description": "the name of the manufacturer of this device",
                  "type": "string"
                }
              },
              "type": "object",
              "additionalProperties": false
            },
            "ElectrodeGroup": {
              "required": [
                "name",
                "description",
                "location",
                "device"
              ],
              "properties": {
                "name": {
                  "description": "the name of this electrode group",
                  "type": "string"
                },
                "description": {
                  "description": "description of this electrode group",
                  "type": "string"
                },
                "location": {
                  "description": "description of location of this electrode group",
                  "type": "string"
                },
                "device": {
                  "description": "the device that was used to record from this electrode group",
                  "type": "string",
                  "target": "pynwb.device.Device"
                }
              },
              "type": "object",
              "additionalProperties": false,
              "tag": "pynwb.ecephys.ElectrodeGroup"
            },
            "Electrodes": {
              "type": "object",
              "additionalProperties": false,
              "required": [
                "name"
              ],
              "properties": {
                "name": {
                  "type": "string",
                  "description": "name of this electrodes column"
                },
                "description": {
                  "type": "string",
                  "description": "description of this electrodes column"
                }
              }
          }
        }
      },
      "type": "object",
      "additionalProperties": false,
      "$schema": "http://json-schema.org/draft-07/schema#",
      "$id": "metadata.schema.json",
      "title": "Metadata",
      "description": "Schema for the metadata",
      "version": "0.1.0"
    }

Like with the source schemas, :py:class:`.NWBConverter` merges together metadata schemas are combined across
each of its ``DataInterface`` s automatically and the result can be obtained by calling the ``.get_metadata_schema()`` method
of an instance of the custom :py:class:`.NWBConverter`. However, with metadata, the underlying schemas are
merged directly with each other instead of being joined together. For more information on how these nested
dictionaries automatically merge, refer to :py:func:`~neuroconv.utils.dict.dict_deep_update`.
