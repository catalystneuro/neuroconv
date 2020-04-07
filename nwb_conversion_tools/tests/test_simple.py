# Simple tests to kickstart the testing of nwb-conversion-tools


def test_base_class():
    from nwb_conversion_tools.converter import NWBConverter
    from datetime import datetime
    import yaml

    # Load metadata from YAML file
    metafile = 'metafile_tests.yml'
    with open(metafile) as f:
        metadata = yaml.safe_load(f)

    # Make converter
    converter = NWBConverter(metadata=metadata)

    # Test basic fields
    assert converter.nwbfile.experimenter[0] == 'Mr Tester'
    assert converter.nwbfile.identifier == 'abc123'
    assert isinstance(converter.nwbfile.session_start_time, datetime)

    # Test subject
    assert converter.nwbfile.subject.sex == 'M'
    assert converter.nwbfile.subject.weight == '10g'
    assert isinstance(converter.nwbfile.subject.date_of_birth, datetime)
