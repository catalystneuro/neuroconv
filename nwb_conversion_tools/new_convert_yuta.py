
from NWBConverter import BuzsakiLabNWBConverter

# usage
input_file_schema = BuzsakiLabNWBConverter.get_input_schema()

# construct input_args dict according to input schema, e.g.: 
input_args = {'neuroscope': {'file_path': "D:/BuzsakiData/SenzaiY/YutaMouse41/YutaMouse41-150903/YutaMouse41-150903.dat"}}

buzlab_converter = BuzsakiLabNWBConverter(**input_args)

expt_json_schema = buzlab_converter.get_metadata_schema()

# construct metadata_dict according to expt_json_schema, e.g. 
metadata_dict = {
    'neuroscope': {
        'Device': {
            'name': 'Device',
            'description': 'no description'
        },
        'ElectrodeGroup': {
            'name': 'ElectrodeGroup',
            'description': 'no description'
        },        
        'ElectricalSeries': {
            'name': 'ElectricalSeries',
            'description': 'no description'
        }
    }
}

nwbfile_path = 'D:/BuzsakiData/SenzaiY/YutaMouse41/YutaMouse41-150903_new_converter.nwb'
buzlab_converter.run_conversion(nwbfile_path, metadata_dict, stub_test=True)

