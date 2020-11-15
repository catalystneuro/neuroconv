## DataInterfaces and Converters

**DataInterfaces** are classes that interface specific data types with NWB. DataInterfaces are the specialist building blocks of any conversion task. <br>
**Converters** are classes responsible for combining and coordinating the operations of multiple DataInterfaces in order to assemble the output of complex neurophysiology experiments into a single, time-aligned NWB file.

Any conversion task requires two sets of information:
- Input data
- Metadata

Users can edit entries in these sets through [graphical user interface forms](https://github.com/catalystneuro/nwb-web-gui) and through command line interface for every Converter.


## Input schema and data

The **input schema** is a JSON schema that defines the rules for organizing the **input data**. Input data has two main properties: <br>
1. Paths to source data files and directories
2. Boolean options to control the conversion process

**DataInterface** classes have the abstract method `get_input_schema()` which is responsible to return a dictionary compliant with the general input schema structure. For example, a hypothetical **EcephysDataInterface**, dealing extracellular electrophysiology data, would return:


<details>
<summary>
  <strong>EcephysDataInterface input schema</strong>
</summary>

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "source.schema.json",
  "title": "Source data and conversion options",
  "description": "Schema for the source data and conversion options",
  "version": "0.1.0",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "source_data": {
      "title": "Source Data",
      "type": "object",
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
    },
    "conversion_options": {
      "title": "Conversion Options",
      "type": "object",
      "properties": {
        "ecephys_option_1": {
          "type": "boolean",
          "default": true
        },
        "ecephys_option_2": {
          "type": "boolean",
          "default": true
        }
      }
    }
  }
}
```
</details>
<br>

A hypothetical **OphysDataInterface** class would return a similar dictionary, with properties related to optophysiology data. Now any lab that has simultaneous ecephys and ophys recordings that could be interfaced with those classes can combine them using a converter. This hypothetical **LabConverter** is then responsible for combining **EcephysDataInterface** and **OphysDataInterface** operations and its `get_input_schema()` method would return:

<details>
<summary>
  <strong>LabConverter input schema</strong>
</summary>

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "source.schema.json",
  "title": "Source data and conversion options",
  "description": "Schema for the source data and conversion options",
  "version": "0.1.0",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "source_data": {
      "title": "Source Data",
      "type": "object",
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
          "format": "file",
          "description": "path to file containing processed ophys data files"
        }
      }
    },
    "conversion_options": {
      "title": "Conversion Options",
      "type": "object",
      "properties": {
        "ecephys_option_1": {
          "type": "boolean",
          "default": true
        },
        "ecephys_option_2": {
          "type": "boolean",
          "default": true
        },
        "ophys_option_1": {
          "type": "boolean",
          "default": true
        },
        "ophys_option_2": {
          "type": "boolean",
          "default": true
        }
      }
    }
  }
}
```

</details>
<br>

The input schema for LabConverter therefore defines all the fields and how they should be filled for a conversion task from this specific ecephys/ophys experiment to a NWB file.


## Metadata schema and data

The **metadata schema** is a JSON schema that defines the rules for organizing the NWB file **metadata**. The metadata properties map to the NWB classes necessary for any specific conversion task.

Similar to input data, each DataInterface produces its own metadata schema reflecting the specificities of the dataset it interfaces with. The DataInterface specific metadata schema can be obtained via method `get_metadata_schema()`. For example, the EcephysDataInterface could return a metadata schema similar to this:

<details>
<summary>
  <strong>EcephysDataInterface metadata schema</strong>
</summary>

```json
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
```

</details>
<br>

Each DataInterface also provides a way to automatically fetch as much metadata as possible directly from the dataset it interfaces with. This is done with the method `get_metadata()`.

OphysDataInterface would return a similar dictionaries for metadata_schema and metadata, with properties related to optophysiology data. The LabConverter will combine the DataInterfaces specific schemas and metadatas into a full dictionaries, and potentially include properties that lie outside the scope of specific DataInterfaces.


## Step-by-step operations

1. LabConverter.get_input_schema()  
    1.1 Loop through DataInterface.get_input_schema()  
    1.2 Combine returned schemas  
    1.3* Create Input Forms  

2. Get user-input input_data that complies to the returned full input_schema

3. Instantiate LabConverter(input_data)  
    3.1 Instantiate all DataInterface(input_data)

4. LabConverter.get_metadata_schema()  
    4.1 Loop through DataInterface.get_metadata_schema()  
    4.2 Combine returned schemas  
    4.3* Create Metadata Forms  

5. Automatically fetches available metadata with LabConverter.get_metadata()  
    5.1 Loop through DataInterface.get_metadata()  
    5.2 Combine returned metadata  
    5.3 Include lab-specific metadata not fetched by DataInterfaces  
    5.4* Pre-fill Metadata Forms with fetched metadata  

6. Get user-input metadata that complies to the returned full metadata_schema  

7. Run conversion with LabConverter.run_conversion(metadata)  
    7.1 Loop through DataInterface.convert_data(metadata)  

\* When Converter interfaces with GUI Forms

![](converter-gui-operations.png)
