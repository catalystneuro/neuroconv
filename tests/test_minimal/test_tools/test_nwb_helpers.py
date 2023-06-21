from datetime import datetime

from hdmf.testing import TestCase
from pynwb import ProcessingModule
from jsonschema.exceptions import ValidationError

from neuroconv.tools.nwb_helpers import get_module, make_nwbfile_from_metadata


class TestNWBHelpers(TestCase):
    def test_get_module(self):
        nwbfile = make_nwbfile_from_metadata(
            metadata=dict(NWBFile=dict(session_start_time=datetime.now().astimezone()))
        )

        name_1 = "test_1"
        name_2 = "test_2"
        description_1 = "description_1"
        description_2 = "description_2"
        nwbfile.create_processing_module(name=name_1, description=description_1)
        mod_1 = get_module(nwbfile=nwbfile, name=name_1, description=description_1)
        mod_2 = get_module(nwbfile=nwbfile, name=name_2, description=description_2)
        assert isinstance(mod_1, ProcessingModule)
        assert mod_1.description == description_1
        assert isinstance(mod_2, ProcessingModule)
        assert mod_2.description == description_2
        self.assertWarns(UserWarning, get_module, **dict(nwbfile=nwbfile, name=name_1, description=description_2))

    def test_make_nwbfile_from_metadata_empty(self):
        with self.assertRaises(ValidationError):
            make_nwbfile_from_metadata(metadata=dict())

    def test_make_nwbfile_from_metadata_session_start_time(self):
        with self.assertRaises(ValidationError):
            make_nwbfile_from_metadata(
                metadata=dict(NWBFile=dict(session_description="Mouse exploring an open field"))
            )