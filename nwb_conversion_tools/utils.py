"""Authors: Cody Baker, Ben Dichter and Luiz Tauffer."""
import inspect
from datetime import datetime
import collections.abc

import numpy as np
import pynwb


def get_schema_data(in_data, data_schema):
    """Output the parts of the input dictionary in_data that are within the json schema properties of data_schema."""
    return {k: in_data[k] for k in data_schema['properties'] if k in in_data}


def dict_deep_update(d, u):
    """Perform an update to all nested keys of dictionary d from dictionary u."""
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = dict_deep_update(d.get(k, {}), v)
        elif isinstance(v, list):
            d[k] = d.get(k, []) + v
            # Remove repeated items if they exist
            if len(v) > 0 and not isinstance(v[0], dict):
                d[k] = list(np.unique(d[k]))
        else:
            d[k] = v
    return d


def get_base_schema(tag=None):
    base_schema = dict(
        required=[],
        properties={},
        type='object',
        additionalProperties=False
    )
    if tag is not None:
        base_schema.update(tag=tag)
    return base_schema


def get_root_schema():
    root_schema = get_base_schema()
    root_schema.update({
        "$schema": "http://json-schema.org/draft-07/schema#",
    })
    return root_schema


def get_base_source_schema():
    source_schema = get_root_schema()
    source_schema.update({
        "$id": "source.schema.json",
        "title": "Source data schema",
        "description": "Schema for the source data, files and directories",
        "version": "0.1.0",
    })
    return source_schema


def get_base_conversion_options_schema():
    conversion_options_schema = get_root_schema()
    conversion_options_schema.update({
        "$id": "conversion_options.schema.json",
        "title": "Conversion options schema",
        "description": "Schema for the conversion options",
        "version": "0.1.0",
    })
    return conversion_options_schema


def get_base_metadata_schema():
    metadata_schema = get_root_schema()
    metadata_schema.update({
        "$id": "metadata.schema.json",
        "title": "Metadata",
        "description": "Schema for the metadata",
        "version": "0.1.0",
        "required": ["NWBFile"],
    })
    return metadata_schema


def get_schema_from_method_signature(class_method, exclude=None):
    if exclude is None:
        exclude = []
    input_schema = get_base_schema()
    for param in inspect.signature(class_method).parameters.values():
        if param.name != 'self':
            arg_spec = {
                param.name: dict(
                    type='string'
                )
            }
            if param.default is param.empty:
                input_schema['required'].append(param.name)
            elif param.default is not None:
                arg_spec[param.name].update(default=param.default)
            input_schema['properties'].update(arg_spec)
        input_schema['additionalProperties'] = param.kind == inspect.Parameter.VAR_KEYWORD

    return input_schema


def get_schema_from_hdmf_class(hdmf_class):
    """Get metadata schema from hdmf class."""
    schema = get_base_schema()
    schema['tag'] = hdmf_class.__module__ + '.' + hdmf_class.__name__

    pynwb_children_fields = [f['name'] for f in hdmf_class.get_fields_conf() if f.get('child', False)]

    docval = hdmf_class.__init__.__docval__
    for docval_arg in docval['args']:
        schema_arg = {docval_arg['name']: dict(description=docval_arg['doc'])}

        # type float
        if docval_arg['type'] == 'float' \
            or (isinstance(docval_arg['type'], tuple)
                and 'float' in docval_arg['type']):
            schema_arg[docval_arg['name']].update(type='number')

        # type string
        elif docval_arg['type'] is str \
            or (isinstance(docval_arg['type'], tuple)
                and str in docval_arg['type']):
            schema_arg[docval_arg['name']].update(type='string')

        # type datetime
        elif docval_arg['type'] is datetime \
            or (isinstance(docval_arg['type'], tuple)
                and datetime in docval_arg['type']):
            schema_arg[docval_arg['name']].update(type='string', format='date-time')

        # if TimeSeries, skip it
        elif docval_arg['type'] is pynwb.base.TimeSeries \
            or (isinstance(docval_arg['type'], tuple)
                and pynwb.base.TimeSeries in docval_arg['type']):
            continue

        # if PlaneSegmentation, skip it
        elif docval_arg['type'] is pynwb.ophys.PlaneSegmentation or \
                (isinstance(docval_arg['type'], tuple) and
                 pynwb.ophys.PlaneSegmentation in docval_arg['type']):
            continue

        else:
            if not isinstance(docval_arg['type'], tuple):
                docval_arg_type = [docval_arg['type']]
            else:
                docval_arg_type = docval_arg['type']

            # if another nwb object (or list of nwb objects)
            if any([t.__module__.split('.')[0] == 'pynwb' for t in docval_arg_type if hasattr(t, '__module__')]):
                is_nwb = [t.__module__.split('.')[0] == 'pynwb' for t in list(docval_arg_type) if
                          hasattr(t, '__module__')]
                item = docval_arg_type[np.where(is_nwb)[0][0]]
                # if it is child
                if docval_arg['name'] in pynwb_children_fields:
                    items = [get_schema_from_hdmf_class(item)]
                    schema_arg[docval_arg['name']].update(
                        type='array', items=items, minItems=1, maxItems=1
                    )
                # if it is link
                else:
                    target = item.__module__ + '.' + item.__name__
                    schema_arg[docval_arg['name']].update(
                        type='string',
                        target=target
                    )
            else:
                continue

        # Check for default arguments
        if 'default' in docval_arg:
            if docval_arg['default'] is not None:
                schema_arg[docval_arg['name']].update(default=docval_arg['default'])
        else:
            schema['required'].append(docval_arg['name'])

        schema['properties'].update(schema_arg)

    if 'allow_extra' in docval:
        schema['additionalProperties'] = docval['allow_extra']

    return schema


def get_schema_for_NWBFile():
    schema = get_base_schema()
    schema['tag'] = 'pynwb.file.NWBFile'
    schema['required'] = ["session_description", "identifier", "session_start_time"]
    schema['properties'] = {
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
        },
        "experimenter": {
            "type": "array",
            "items": {"type": "string", "title": "experimenter"},
            "description": "name of person who performed experiment"
        },
        "experimentd_description": {
            "type": "string",
            "description": "general description of the experiment"
        },
        "sessiond_id": {
            "type": "string",
            "description": "lab-specific ID for the session"
        },
        "institution": {
            "type": "string",
            "description": "institution(s) where experiment is performed"
        },
        "notes": {
            "type": "string",
            "description": "Notes about the experiment."
        },
        "pharmacology": {
            "type": "string",
            "description": "Description of drugs used, including how and when they were administered. Anesthesia(s), "
                           "painkiller(s), etc., plus dosage, concentration, etc."
        },
        "protocol": {
            "type": "string",
            "description": "Experimental protocol, if applicable. E.g., include IACUC protocol"
        },
        "related_publications": {
            "type": "string",
            "description": "Publication information.PMID, DOI, URL, etc. If multiple, concatenate together and describe"
                           " which is which. such as PMID, DOI, URL, etc"
        },
        "slices": {
            "type": "string",
            "description": "Description of slices, including information about preparation thickness, orientation, "
                           "temperature and bath solution"
        },
        "source_script": {
            "type": "string",
            "description": "Script file used to create this NWB file."
        },
        "source_script_file_name": {
            "type": "string",
            "description": "Name of the source_script file"
        },
        "data_collection": {
            "type": "string",
            "description": "Notes about data collection and analysis."
        },
        "surgery": {
            "type": "string",
            "description": "Narrative description about surgery/surgeries, including date(s) and who performed surgery."
        },
        "virus": {
            "type": "string",
            "description": "Information about virus(es) used in experiments, including virus ID, source, date made, "
                           "injection location, volume, etc."
        },
        "stimulus_notes": {
            "type": "string",
            "description": "Notes about stimuli, such as how and where presented."
        },
        "lab": {
            "type": "string",
            "description": "lab where experiment was performed"
        }
    }
    return schema
