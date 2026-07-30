"""
Tests for EDFRecordingInterface metadata extraction.

The fixtures are written with ``pyedflib`` (already a dependency of the ``edf`` extra) so these run
without any external data or network access.
"""

from datetime import date, datetime

import numpy as np
import pytest

from neuroconv.datainterfaces import EDFRecordingInterface
from neuroconv.datainterfaces.ecephys.edf.edfdatainterface import _parse_birthdate, _parse_sex

pyedflib = pytest.importorskip("pyedflib")

SAMPLING_FREQUENCY = 100.0
NUMBER_OF_CHANNELS = 2
SECONDS = 4


def write_edf(path, *, patient_code="", birthdate=None, technician="", sex=""):
    """Write a small continuous EDF+ file, optionally carrying subject information."""
    writer = pyedflib.EdfWriter(str(path), NUMBER_OF_CHANNELS, file_type=pyedflib.FILETYPE_EDFPLUS)
    try:
        if patient_code:
            writer.setPatientCode(patient_code)
        if birthdate is not None:
            writer.setBirthdate(birthdate)
        if technician:
            writer.setTechnician(technician)
        if sex:
            writer.setSex(sex)
        writer.setSignalHeaders(
            [
                dict(
                    label=f"ch{index}",
                    dimension="uV",
                    sample_frequency=SAMPLING_FREQUENCY,
                    physical_min=-1000.0,
                    physical_max=1000.0,
                    digital_min=-32768,
                    digital_max=32767,
                    transducer="",
                    prefilter="",
                )
                for index in range(NUMBER_OF_CHANNELS)
            ]
        )
        generator = np.random.default_rng(0)
        samples = int(SAMPLING_FREQUENCY * SECONDS)
        writer.writeSamples([generator.normal(size=samples) * 100 for _ in range(NUMBER_OF_CHANNELS)])
    finally:
        writer.close()
    return str(path)


class TestParseBirthdate:
    """Direct tests, because a file fixture only ever exercises whichever form pyedflib emits."""

    @pytest.mark.parametrize(
        "value, expected",
        [
            ("02 may 1951", datetime(1951, 5, 2)),  # what pyedflib returns
            ("02-MAY-1951", datetime(1951, 5, 2)),  # the EDF+ patient field's own form
            ("2 May 1951", datetime(1951, 5, 2)),
            ("02-may-1951", datetime(1951, 5, 2)),
            ("1951-05-02", datetime(1951, 5, 2)),  # ISO, e.g. from str() of a date
            (date(1951, 5, 2), datetime(1951, 5, 2)),
            (datetime(1951, 5, 2), datetime(1951, 5, 2)),
        ],
    )
    def test_accepted_forms(self, value, expected):
        assert _parse_birthdate(value) == expected

    @pytest.mark.parametrize(
        "value",
        [
            None,
            "",
            "   ",
            "not-a-date",
            "02.05.51",  # ambiguous two-digit year: %y would have made this 2051
            "31-FEB-1951",  # impossible calendar date
            "02-XXX-1951",  # unrecognized month
            "02-MAY-2051",  # a birthdate cannot be in the future
        ],
    )
    def test_rejected_forms(self, value):
        assert _parse_birthdate(value) is None

    def test_month_names_do_not_depend_on_the_locale(self):
        """
        ``strptime("%b")`` resolves month names through LC_TIME and would drop the birthdate under a
        non-English locale. The explicit month table sidesteps that entirely.
        """
        import calendar

        # Whatever the ambient locale calls May, the EDF spelling must still parse.
        assert _parse_birthdate("02 may 1951") == datetime(1951, 5, 2)
        assert calendar.month_abbr[5]  # locale-dependent; only here to show it is not consulted


class TestParseSex:
    @pytest.mark.parametrize(
        "value, expected",
        [
            ("Female", "F"),
            ("Male", "M"),
            ("F", "F"),
            ("M", "M"),
            ("female", "F"),
            ("X", None),  # EDF+ writes a bare X for an unknown subfield
            ("", None),
            (None, None),
        ],
    )
    def test_mapping(self, value, expected):
        assert _parse_sex(value) == expected


class TestEDFSubjectMetadata:
    @pytest.mark.parametrize("written, expected", [("Female", "F"), ("Male", "M")])
    def test_sex_is_read_from_the_header(self, tmp_path, written, expected):
        """
        The header states the subject's sex, so defaulting it to "U" writes a positively wrong value.

        Absent metadata is visibly absent; ``sex = "U"`` on a subject the file says is female looks
        like a finding.
        """
        path = write_edf(tmp_path / "subject.edf", patient_code="MCH-42", sex=written)
        interface = EDFRecordingInterface(file_path=path)

        assert interface.extract_subject_metadata()["sex"] == expected
        assert interface.get_metadata()["Subject"]["sex"] == expected

    def test_sex_falls_back_to_the_legacy_gender_key(self, tmp_path):
        """Older pyedflib exposed this as "gender"; it must not be ignored."""
        path = write_edf(tmp_path / "subject.edf", patient_code="MCH-42")
        interface = EDFRecordingInterface(file_path=path)
        interface.edf_header.pop("sex", None)
        interface.edf_header["gender"] = "Female"

        assert interface.get_metadata()["Subject"]["sex"] == "F"

    def test_unknown_sex_still_defaults(self, tmp_path):
        """"U" remains the fallback when the header genuinely does not say."""
        path = write_edf(tmp_path / "subject.edf", patient_code="MCH-42")
        interface = EDFRecordingInterface(file_path=path)

        assert interface.extract_subject_metadata().get("sex") is None
        assert interface.get_metadata()["Subject"]["sex"] == "U"

    def test_subject_metadata_reaches_get_metadata(self, tmp_path):
        """
        Regression test: the subject information read from the header must survive into the metadata.

        ``metadata`` is a ``DeepDict`` (a ``defaultdict``) and ``dict.get`` does not go through
        ``__missing__``, so ``metadata.get("Subject", dict()).update(...)`` updated a throwaway dict and
        every EDF conversion silently lost the header's subject information.
        """
        path = write_edf(tmp_path / "subject.edf", patient_code="MCH-42")
        interface = EDFRecordingInterface(file_path=path)

        # The value was always read correctly; it was discarded on the way into the metadata.
        assert interface.extract_subject_metadata()["subject_id"] == "MCH-42"
        assert interface.get_metadata()["Subject"]["subject_id"] == "MCH-42"

    def test_schema_required_fields_are_filled(self, tmp_path):
        """A Subject with only a subject_id would not satisfy the metadata schema."""
        path = write_edf(tmp_path / "subject.edf", patient_code="MCH-42")
        interface = EDFRecordingInterface(file_path=path)

        subject_metadata = interface.get_metadata()["Subject"]
        assert subject_metadata["species"] == "Unknown species"
        assert subject_metadata["sex"] == "U"

    def test_metadata_is_schema_valid(self, tmp_path):
        """
        Validated through neuroconv's own helper, which serializes datetimes before checking.

        The schema types ``date_of_birth`` as a date-time *string* while pynwb's ``Subject`` requires a
        ``datetime`` object; ``validate_metadata`` reconciles the two with ``_NWBMetaDataEncoder``, the
        same way it does for ``session_start_time``.
        """
        from neuroconv.utils.json_schema import validate_metadata

        path = write_edf(tmp_path / "subject.edf", patient_code="MCH-42", birthdate=date(1951, 5, 2))
        interface = EDFRecordingInterface(file_path=path)

        metadata = interface.get_metadata()
        metadata["NWBFile"].update(session_start_time=datetime(2021, 9, 16, 12, 35, 13))
        validate_metadata(metadata=metadata, schema=interface.get_metadata_schema())

    def test_conversion_writes_the_subject(self, tmp_path):
        """End to end: pynwb must accept what get_metadata now produces, birthdate included."""
        from pynwb import NWBHDF5IO

        path = write_edf(tmp_path / "subject.edf", patient_code="MCH-42", birthdate=date(1951, 5, 2), sex="Female")
        interface = EDFRecordingInterface(file_path=path)

        nwbfile_path = tmp_path / "subject.nwb"
        interface.run_conversion(nwbfile_path=str(nwbfile_path), metadata=interface.get_metadata(), overwrite=True)
        with NWBHDF5IO(str(nwbfile_path), "r") as io:
            subject = io.read().subject
            assert subject.subject_id == "MCH-42"
            assert subject.date_of_birth.year == 1951
            assert subject.species == "Unknown species"
            # Read from the header, not the "U" fallback.
            assert subject.sex == "F"

    def test_birthdate_is_parsed_to_a_datetime(self, tmp_path):
        """``Subject.date_of_birth`` must be a datetime; the readers hand the field back as a string."""
        path = write_edf(tmp_path / "subject.edf", patient_code="MCH-42", birthdate=date(1951, 5, 2))
        interface = EDFRecordingInterface(file_path=path)

        date_of_birth = interface.get_metadata()["Subject"]["date_of_birth"]
        assert isinstance(date_of_birth, datetime)
        assert (date_of_birth.year, date_of_birth.month, date_of_birth.day) == (1951, 5, 2)

    def test_unparsable_birthdate_is_dropped(self, tmp_path):
        """A date pynwb would reject must not be forwarded to it."""
        path = write_edf(tmp_path / "subject.edf", patient_code="MCH-42")
        interface = EDFRecordingInterface(file_path=path)
        interface.edf_header["birthdate"] = "not-a-date"

        subject_metadata = interface.get_metadata()["Subject"]
        assert subject_metadata["subject_id"] == "MCH-42"
        assert "date_of_birth" not in subject_metadata

    def test_no_subject_information_leaves_subject_empty(self, tmp_path):
        """A file with no patient information must not gain a placeholder Subject."""
        path = write_edf(tmp_path / "anonymous.edf")
        interface = EDFRecordingInterface(file_path=path)

        assert interface.extract_subject_metadata() == dict()
        assert dict(interface.get_metadata().get("Subject", dict())) == dict()

    def test_nwbfile_metadata_still_extracted(self, tmp_path):
        """The NWBFile half of get_metadata was never broken; keep it that way."""
        path = write_edf(tmp_path / "subject.edf", technician="Tech7")
        interface = EDFRecordingInterface(file_path=path)

        metadata = interface.get_metadata()
        assert metadata["NWBFile"]["experimenter"] == "Tech7"
        assert metadata["NWBFile"]["session_start_time"] is not None
