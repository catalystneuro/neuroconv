import datetime

import numpy as np
import pytest

from neuroconv.datainterfaces import EDFRecordingInterface

pyedflib = pytest.importorskip("pyedflib")


def write_edf_file(file_path, *, birthdate=None, patient_code="MCH-42"):
    """Write a two-channel EDF+ file, optionally stating a birthdate in the patient field."""
    writer = pyedflib.EdfWriter(str(file_path), 2, file_type=pyedflib.FILETYPE_EDFPLUS)
    writer.setPatientCode(patient_code)
    writer.setSex(1)
    if birthdate is not None:
        writer.setBirthdate(birthdate)
    writer.setStartdatetime(datetime.datetime(2020, 1, 1, 12, 0, 0))
    writer.setSignalHeaders(
        [
            dict(
                label=f"ch{channel}",
                dimension="uV",
                sample_frequency=100,
                physical_max=1000.0,
                physical_min=-1000.0,
                digital_max=32767,
                digital_min=-32768,
                transducer="",
                prefilter="",
            )
            for channel in range(2)
        ]
    )
    writer.writeSamples([np.zeros(100), np.zeros(100)])
    writer.close()
    return file_path


def test_date_of_birth_is_read_from_the_patient_field(tmp_path):
    file_path = write_edf_file(tmp_path / "with_birthdate.edf", birthdate=datetime.date(1951, 5, 2))

    interface = EDFRecordingInterface(file_path=file_path)
    metadata = interface.get_metadata()

    assert metadata["Subject"]["date_of_birth"] == "1951-05-02"


def test_a_file_that_states_no_birthdate_reports_none(tmp_path):
    file_path = write_edf_file(tmp_path / "no_birthdate.edf")

    interface = EDFRecordingInterface(file_path=file_path)
    metadata = interface.get_metadata()

    assert "date_of_birth" not in metadata["Subject"]


def test_the_written_subject_carries_the_birthdate(tmp_path):
    file_path = write_edf_file(tmp_path / "written.edf", birthdate=datetime.date(1951, 5, 2))

    interface = EDFRecordingInterface(file_path=file_path)
    metadata = interface.get_metadata()
    metadata["Subject"].update(species="Homo sapiens")
    nwbfile = interface.create_nwbfile(metadata=metadata)

    # pynwb attaches the writing machine's timezone to a naive datetime, and the header states a date
    # rather than an instant, so the date is what is asserted.
    assert nwbfile.subject.date_of_birth.date() == datetime.date(1951, 5, 2)


@pytest.mark.parametrize("birthdate", ["", "X", "not a date", "02 xxx 1951", "31 feb 1951", "02 may"])
def test_a_birthdate_that_is_not_a_date_is_dropped_rather_than_raising(birthdate):
    from neuroconv.datainterfaces.ecephys.edf.edfdatainterface import _parse_birthdate

    assert _parse_birthdate(birthdate) is None
