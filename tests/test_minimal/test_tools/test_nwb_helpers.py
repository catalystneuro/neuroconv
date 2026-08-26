from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo

from hdmf.testing import TestCase
from jsonschema.exceptions import ValidationError
from pynwb import ProcessingModule

from neuroconv.tools.nwb_helpers import (
    add_subject_to_nwbfile,
    get_module,
    make_nwbfile_from_metadata,
)


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
        session_start_time = datetime(2023, 6, 22, 9, 0, 0, tzinfo=ZoneInfo("America/New_York"))
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
        # `date_of_birth` is stated as a string because that is the entry the conversion rewrites, and
        # writing the datetime back into the caller's dictionary is what this test exists to catch.
        metadata = dict(
            NWBFile=dict(session_start_time=datetime.now().astimezone()),
            Subject=dict(
                subject_id="test",
                sex="M",
                species="Mus musculus",
                date_of_birth="2025-06-01T00:00:00+00:00",
            ),
        )
        expected_metadata = deepcopy(metadata)
        make_nwbfile_from_metadata(metadata=metadata)
        assert metadata == expected_metadata

    def test_add_subject_to_nwbfile_without_a_subject_block(self):
        """A source that recorded no subject leaves the file without one rather than raising."""
        nwbfile = make_nwbfile_from_metadata(
            metadata=dict(NWBFile=dict(session_start_time=datetime.now().astimezone()))
        )

        add_subject_to_nwbfile(nwbfile=nwbfile, metadata=dict(NWBFile=dict()))

        assert nwbfile.subject is None

    def test_add_subject_to_nwbfile_on_a_file_that_has_one(self):
        """An NWBFile describes one subject, so a second one is a conflict for the caller to resolve."""
        metadata = dict(
            NWBFile=dict(session_start_time=datetime.now().astimezone()),
            Subject=dict(subject_id="the_first_one", sex="M", species="Mus musculus"),
        )
        nwbfile = make_nwbfile_from_metadata(metadata=metadata)

        second_metadata = dict(Subject=dict(subject_id="the_second_one", sex="F", species="Mus musculus"))
        with self.assertRaisesWith(
            exc_type=ValueError,
            exc_msg=(
                "This NWBFile already holds the subject 'the_first_one' and an NWBFile describes one subject. "
                "The metadata states 'the_second_one'. Write the two subjects to separate files, or drop "
                "metadata['Subject'] to keep the one already there."
            ),
        ):
            add_subject_to_nwbfile(nwbfile=nwbfile, metadata=second_metadata)
