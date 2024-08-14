import sys
from datetime import datetime
from io import StringIO
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import patch

import h5py
import pytest
from hdmf.testing import TestCase
from hdmf_zarr import NWBZarrIO
from pynwb import NWBHDF5IO, TimeSeries
from pynwb.testing.mock.base import mock_TimeSeries
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.nwb_helpers import make_nwbfile_from_metadata, make_or_load_nwbfile


class TestMakeOrLoadNWBFile(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmpdir = Path(mkdtemp())
        cls.metadata = dict(NWBFile=dict(session_start_time=datetime.now().astimezone()))

    @classmethod
    def tearDownClass(cls):
        rmtree(cls.tmpdir)

    def setUp(self):
        self.time_series_1 = TimeSeries(name="test1", data=[1], rate=1.0, unit="test")
        self.time_series_2 = TimeSeries(name="test2", data=[1], rate=1.0, unit="test")

    def test_make_or_load_nwbfile_assertion_nwbfile_path_and_nwbfile_object(self):
        """Test if assertion is raised when specifying both an NWBFile path and an in-memory NWBFile object."""
        with self.assertRaisesWith(
            exc_type=AssertionError,
            exc_msg=(
                "You must specify either an 'nwbfile_path', or an in-memory 'nwbfile' object, "
                "or provide the metadata for creating one."
            ),
        ):
            with make_or_load_nwbfile(verbose=True) as nwbfile:
                nwbfile.add_acquisition(self.time_series_1)

    def test_make_or_load_nwbfile_assertion_conflicting_bases(self):
        """Test if assertion is raised when conflicting nwbfile object bases are used."""
        nwbfile_path = self.tmpdir / "test_make_or_load_nwbfile_assertion_conflicting_bases.nwb"
        with make_or_load_nwbfile(nwbfile_path=nwbfile_path, metadata=self.metadata, overwrite=True) as nwbfile:
            nwbfile.add_acquisition(self.time_series_1)

        with self.assertRaisesWith(
            exc_type=AssertionError,
            exc_msg=(
                "'nwbfile_path' exists at location, 'overwrite' is False (append mode), but an in-memory 'nwbfile' "
                "object was passed! Cannot reconcile which nwbfile object to write."
            ),
        ):
            with make_or_load_nwbfile(
                nwbfile_path=nwbfile_path, nwbfile=make_nwbfile_from_metadata(metadata=self.metadata), overwrite=False
            ) as nwbfile:
                nwbfile.add_acquisition(self.time_series_1)

    def test_make_or_load_nwbfile_no_print_on_error_in_context(self):
        """Test the expected stdout in case an error occurs during the context."""
        with patch("sys.stdout", new=StringIO()) as fake_out:
            try:
                with make_or_load_nwbfile(nwbfile_path=self.tmpdir / "doesnt_matter_1.nwb", metadata=self.metadata):
                    raise ValueError("test")
            except ValueError:
                pass
            self.assertEqual(fake_out.getvalue(), "")

    def test_make_or_load_nwbfile_no_file_save_on_error_in_context(self):
        nwbfile_path = Path(self.tmpdir / "doesnt_matter_2.nwb")
        try:
            with make_or_load_nwbfile(nwbfile_path=nwbfile_path, metadata=self.metadata):
                raise ValueError("test")
        except ValueError as exception:
            if str(exception) == "test":
                pass
            else:
                raise exception

        # Windows can experience permission issues
        if sys.platform != "win32":
            assert not nwbfile_path.exists()

    def test_make_or_load_nwbfile_write_hdf5(self):
        nwbfile_path = self.tmpdir / "test_make_or_load_nwbfile_write.nwb"
        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path, metadata=self.metadata, overwrite=True, backend="hdf5"
        ) as nwbfile:
            nwbfile.add_acquisition(self.time_series_1)
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile_out = io.read()
            assert "test1" in nwbfile_out.acquisition

    def test_make_or_load_nwbfile_write_zarr(self):
        nwbfile_path = self.tmpdir / "test_make_or_load_nwbfile_write.nwb.zarr"
        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path, metadata=self.metadata, overwrite=True, backend="zarr"
        ) as nwbfile:
            nwbfile.add_acquisition(self.time_series_1)
        with NWBZarrIO(path=str(nwbfile_path), mode="r") as io:
            nwbfile_out = io.read()
            assert "test1" in nwbfile_out.acquisition

    def test_make_or_load_nwbfile_closure(self):
        nwbfile_path = self.tmpdir / "test_make_or_load_nwbfile_closure.nwb"
        with make_or_load_nwbfile(nwbfile_path=nwbfile_path, metadata=self.metadata, overwrite=True) as nwbfile:
            nwbfile.add_acquisition(self.time_series_1)
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile_out = io.read()
            self.assertCountEqual(nwbfile_out.acquisition["test1"].data, self.time_series_1.data)
        assert not nwbfile_out.acquisition["test1"].data  # A closed h5py.Dataset returns false

    def test_make_or_load_nwbfile_overwrite_hdf5(self):
        nwbfile_path = self.tmpdir / "test_make_or_load_nwbfile_overwrite.nwb"
        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path, metadata=self.metadata, overwrite=True, backend="hdf5"
        ) as nwbfile:
            nwbfile.add_acquisition(self.time_series_1)
        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path, metadata=self.metadata, overwrite=True, backend="hdf5"
        ) as nwbfile:
            nwbfile.add_acquisition(self.time_series_2)
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile_out = io.read()
            assert "test1" not in nwbfile_out.acquisition
            assert "test2" in nwbfile_out.acquisition

    def test_make_or_load_nwbfile_overwrite_zarr(self):
        nwbfile_path = self.tmpdir / "test_make_or_load_nwbfile_overwrite.nwb.zarr"
        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path, metadata=self.metadata, overwrite=True, backend="zarr"
        ) as nwbfile:
            nwbfile.add_acquisition(self.time_series_1)
        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path, metadata=self.metadata, overwrite=True, backend="zarr"
        ) as nwbfile:
            nwbfile.add_acquisition(self.time_series_2)
        with NWBZarrIO(path=str(nwbfile_path), mode="r") as io:
            nwbfile_out = io.read()
            assert "test1" not in nwbfile_out.acquisition
            assert "test2" in nwbfile_out.acquisition

    def test_make_or_load_nwbfile_append_hdf5(self):
        nwbfile_path = self.tmpdir / "test_make_or_load_nwbfile_append.nwb"
        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path, metadata=self.metadata, overwrite=True, backend="hdf5"
        ) as nwbfile:
            nwbfile.add_acquisition(self.time_series_1)
        with make_or_load_nwbfile(nwbfile_path=nwbfile_path, overwrite=False, backend="hdf5") as nwbfile:
            nwbfile.add_acquisition(self.time_series_2)
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile_out = io.read()
            assert "test1" in nwbfile_out.acquisition
            assert "test2" in nwbfile_out.acquisition

    # TODO: re-include when https://github.com/hdmf-dev/hdmf-zarr/issues/182 is resolved
    # def test_make_or_load_nwbfile_append_zarr(self):
    #     nwbfile_path = self.tmpdir / "test_make_or_load_nwbfile_append.nwb.zarr"
    #     with make_or_load_nwbfile(
    #         nwbfile_path=nwbfile_path, metadata=self.metadata, overwrite=True, backend="zarr"
    #     ) as nwbfile:
    #         nwbfile.add_acquisition(self.time_series_1)
    #     with make_or_load_nwbfile(nwbfile_path=nwbfile_path, overwrite=False, backend="zarr") as nwbfile:
    #         nwbfile.add_acquisition(self.time_series_2)
    #     with NWBZarrIO(path=str(nwbfile_path), mode="r") as io:
    #         nwbfile_out = io.read()
    #         assert "test1" in nwbfile_out.acquisition
    #         assert "test2" in nwbfile_out.acquisition
    #
    # def test_make_or_load_nwbfile_append_hdf5_using_zarr_error(self):
    #     nwbfile_path = self.tmpdir / "test_make_or_load_nwbfile_append.nwb"
    #     with make_or_load_nwbfile(
    #         nwbfile_path=nwbfile_path, metadata=self.metadata, overwrite=True, backend="hdf5"
    #     ) as nwbfile:
    #         nwbfile.add_acquisition(self.time_series_1)
    #     with self.assertRaisesWith(
    #         exc_type=IOError,
    #         exc_msg="The chosen backend (zarr) is unable to read the file! Please select a different backend.",
    #     ):
    #         with make_or_load_nwbfile(nwbfile_path=nwbfile_path, overwrite=False, backend="zarr") as nwbfile:
    #             nwbfile.add_acquisition(self.time_series_2)

    def test_make_or_load_nwbfile_append_zarr_using_hdf5_error(self):
        nwbfile_path = self.tmpdir / "test_make_or_load_nwbfile_append.nwb.zarr"
        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path, metadata=self.metadata, overwrite=True, backend="zarr"
        ) as nwbfile:
            nwbfile.add_acquisition(self.time_series_1)
        with self.assertRaisesWith(
            exc_type=IOError,
            exc_msg="The chosen backend ('hdf5') is unable to read the file! Please select 'zarr' instead.",
        ):
            with make_or_load_nwbfile(nwbfile_path=nwbfile_path, overwrite=False, backend="hdf5") as nwbfile:
                nwbfile.add_acquisition(self.time_series_2)

    def test_make_or_load_nwbfile_pass_nwbfile(self):
        nwbfile_path = self.tmpdir / "test_make_or_load_nwbfile_pass_nwbfile.nwb"
        nwbfile_in = make_nwbfile_from_metadata(metadata=self.metadata)
        nwbfile_in.add_acquisition(self.time_series_1)
        with make_or_load_nwbfile(nwbfile_path=nwbfile_path, nwbfile=nwbfile_in, overwrite=True) as nwbfile:
            nwbfile.add_acquisition(self.time_series_2)
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile_out = io.read()
            assert "test1" in nwbfile_out.acquisition
            assert "test2" in nwbfile_out.acquisition


def test_make_or_load_nwbfile_on_corrupt_file(tmpdir: Path) -> None:
    """Testing fix to https://github.com/catalystneuro/neuroconv/issues/910."""
    nwbfile_path = tmpdir / "test_make_or_load_nwbfile_on_corrupt_file.nwb"

    with h5py.File(name=nwbfile_path, mode="w") as io:
        pass

    nwbfile_in = mock_NWBFile()
    with make_or_load_nwbfile(nwbfile_path=nwbfile_path, nwbfile=nwbfile_in, overwrite=True) as nwbfile:
        time_series = mock_TimeSeries()
        nwbfile.add_acquisition(time_series)


def test_raise_error_when_metadata_is_empty_and_creation_is_needed(tmpdir):
    nwbfile_path = tmpdir / "test_make_or_load_nwbfile_empty_metadata.nwb"

    with pytest.raises(ValueError):
        with make_or_load_nwbfile(nwbfile_path=nwbfile_path, metadata=None, overwrite=True) as nwbfile:
            pass
