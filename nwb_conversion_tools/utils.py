"""Authors: Cody Baker, Ben Dichter and Luiz Tauffer."""
from datetime import datetime

import numpy as np
import pynwb

from .json_schema_utils import get_base_schema


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
                and any([it in docval_arg['type'] for it in [float, 'float']])):
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
            if any([hasattr(t, '__nwbfields__') for t in docval_arg_type]):
                is_nwb = [hasattr(t, '__nwbfields__') for t in docval_arg_type]
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
