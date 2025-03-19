from copy import deepcopy
from datetime import datetime

import pytz
from hdmf.testing import TestCase
from jsonschema.exceptions import ValidationError
from pynwb import ProcessingModule

from neuroconv.tools.nwb_helpers import get_module, make_nwbfile_from_metadata


class TestNWBHelpers(TestCase):
    def test_make_nwbfile_successful(self):
        """Test a successful creation of an NWBFile from minimal metadata."""
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
        """Test that an empty metadata dict raises a ValidationError."""
        with self.assertRaises(ValidationError):
            make_nwbfile_from_metadata(metadata=dict())

    def test_make_nwbfile_from_metadata_session_start_time(self):
        """Test that a missing session_start_time raises a ValidationError."""
        with self.assertRaises(ValidationError):
            make_nwbfile_from_metadata(metadata=dict(NWBFile=dict(session_description="Mouse exploring an open field")))

    def test_metadata_integrity(self):
        """Test that the original metadata is not modified."""
        session_start_time = datetime(2023, 6, 22, 9, 0, 0, tzinfo=pytz.timezone("America/New_York"))
        session_description = "Original description"
        identifier = "original_identifier"
        metadata = dict(
            NWBFile=dict(
                session_start_time=session_start_time, session_description=session_description, identifier=identifier
            )
        )
        nwbfile = make_nwbfile_from_metadata(metadata=metadata)
        assert metadata["NWBFile"]["session_description"] == session_description
        assert metadata["NWBFile"]["identifier"] == identifier
        assert metadata["NWBFile"]["session_start_time"] == session_start_time

    def test_make_nwbfile_from_metadata_no_in_place_modification(self):
        """A past version of the `make_nwbfile_from_metadata` function would unintentionally modify the `metadata` dictionary in-place."""
        metadata = dict(
            NWBFile=dict(session_start_time=datetime.now().astimezone()),
            Subject=dict(subject_id="test", sex="M", species="Mus musculus"),
        )
        expected_metadata = deepcopy(metadata)
        make_nwbfile_from_metadata(metadata=metadata)
        assert metadata == expected_metadata
