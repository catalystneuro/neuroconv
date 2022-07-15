import os
from datetime import datetime
from tempfile import mkdtemp
from pathlib import Path
from shutil import rmtree

import pytest
import unittest
from pynwb import NWBHDF5IO, ProcessingModule, TimeSeries
from hdmf.testing import TestCase

from nwb_conversion_tools.tools.nwb_helpers import (
    get_module,
    make_nwbfile_from_metadata,
    get_default_nwbfile_metadata,
    make_or_load_nwbfile,
)
from nwb_conversion_tools.tools.data_transfers import (
    get_globus_dataset_content_sizes,
    estimate_s3_conversion_cost,
    estimate_total_conversion_runtime,
    automatic_dandi_upload,
    transfer_globus_content,
    deploy_process,
)

try:
    import globus_cli

    HAVE_GLOBUS, LOGGED_INTO_GLOBUS = True, True
    if not os.popen("globus ls 188a6110-96db-11eb-b7a9-f57b2d55370d").read():
        LOGGED_INTO_GLOBUS = False
except ModuleNotFoundError:
    HAVE_GLOBUS, LOGGED_INTO_GLOBUS = False, False
HAVE_DANDI_KEY = "DANDI_API_KEY" in os.environ


class TestConversionTools(TestCase):
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

    def test_make_nwbfile_from_metadata(self):
        with self.assertRaisesWith(
            exc_type=AssertionError,
            exc_msg=(
                "'session_start_time' was not found in metadata['NWBFile']! Please add the correct start time of the "
                "session in ISO8601 format (%Y-%m-%dT%H:%M:%S) to this key of the metadata."
            ),
        ):
            make_nwbfile_from_metadata(metadata=dict())


@pytest.mark.skipif(
    not (HAVE_GLOBUS and LOGGED_INTO_GLOBUS),
    reason="You must have globus installed and be logged in to run this test!",
)
def test_get_globus_dataset_content_sizes():
    """Test is fixed to a subpath that is somewhat unlikely to change in the future."""
    assert get_globus_dataset_content_sizes(
        globus_endpoint_id="188a6110-96db-11eb-b7a9-f57b2d55370d",
        path="/SenzaiY/YutaMouse41/YutaMouse41-150821/originalClu/",
    ) == {
        "YutaMouse41-150821.clu.1": 819862,
        "YutaMouse41-150821.clu.2": 870498,
        "YutaMouse41-150821.clu.3": 657938,
        "YutaMouse41-150821.clu.4": 829761,
        "YutaMouse41-150821.clu.5": 653502,
        "YutaMouse41-150821.clu.6": 718752,
        "YutaMouse41-150821.clu.7": 644541,
        "YutaMouse41-150821.clu.8": 523422,
        "YutaMouse41-150821.temp.clu.1": 278025,
        "YutaMouse41-150821.temp.clu.2": 359573,
        "YutaMouse41-150821.temp.clu.3": 219280,
        "YutaMouse41-150821.temp.clu.4": 264388,
        "YutaMouse41-150821.temp.clu.5": 217834,
        "YutaMouse41-150821.temp.clu.6": 239890,
        "YutaMouse41-150821.temp.clu.7": 214835,
        "YutaMouse41-150821.temp.clu.8": 174434,
    }


def test_estimate_s3_conversion_cost_standard():
    test_sizes = [
        1,
        100,
        1e3,  # 1 GB
        1e5,  # 100 GB
        1e6,  # 1 TB
        1e7,  # 10 TB
        1e8,  # 100 TB
    ]
    results = [estimate_s3_conversion_cost(total_mb=total_mb) for total_mb in test_sizes]
    assert results == [
        2.9730398740210563e-15,  # 1 MB
        2.973039874021056e-11,  # 100 MB
        2.9730398740210564e-09,  # 1 GB
        2.9730398740210563e-05,  # 100 GB
        0.002973039874021056,  # 1 TB
        0.2973039874021056,  # 10 TB
        29.73039874021056,  # 100 TB
    ]


@pytest.mark.skipif(
    not HAVE_GLOBUS or not LOGGED_INTO_GLOBUS,
    reason="You must have globus installed and be logged in to run this test!",
)
def test_estimate_s3_conversion_cost_from_globus_single_session():
    content_sizes = get_globus_dataset_content_sizes(
        globus_endpoint_id="188a6110-96db-11eb-b7a9-f57b2d55370d",
        path="/SenzaiY/YutaMouse41/YutaMouse41-150821/originalClu/",
    )
    assert estimate_s3_conversion_cost(total_mb=sum(content_sizes.values()) / 1e6) == 1.756555806400279e-13


@pytest.mark.skipif(
    not HAVE_GLOBUS or not LOGGED_INTO_GLOBUS,
    reason="You must have globus installed and be logged in to run this test!",
)
def test_estimate_s3_conversion_cost_from_globus_multiple_sessions():
    all_content_sizes = {
        session_name: get_globus_dataset_content_sizes(
            globus_endpoint_id="188a6110-96db-11eb-b7a9-f57b2d55370d",
            path=f"/SenzaiY/YutaMouse41/{session_name}",
        )
        for session_name in ["YutaMouse41-150821", "YutaMouse41-150829"]
    }
    assert (
        sum(
            [
                estimate_s3_conversion_cost(total_mb=sum(content_sizes.values()) / 1e6)
                for content_sizes in all_content_sizes.values()
            ]
        )
        == 1.3393785277236152e-07
    )


def test_estimate_total_conversion_runtime():
    test_sizes = [
        1,
        100,
        1e3,  # 1 GB
        1e5,  # 100 GB
        1e6,  # 1 TB
        1e7,  # 10 TB
        1e8,  # 100 TB
    ]
    results = [estimate_total_conversion_runtime(total_mb=total_mb) for total_mb in test_sizes]
    assert results == [
        0.12352941176470589,
        12.352941176470589,
        123.52941176470588,
        12352.94117647059,
        123529.41176470589,
        1235294.1176470588,
        12352941.176470589,
    ]


@pytest.mark.skipif(
    not HAVE_DANDI_KEY,
    reason="You must set your DANDI_API_KEY to run this test!",
)
class TestAutomaticDANDIUpload(TestCase):
    def setUp(self):
        self.tmpdir = Path(mkdtemp())
        self.nwb_folder_path = self.tmpdir / "test_nwb"
        self.nwb_folder_path.mkdir()
        metadata = get_default_nwbfile_metadata()
        metadata["NWBFile"].update(session_start_time=datetime.now().astimezone())
        metadata.update(Subject=dict(subject_id="foo"))
        with NWBHDF5IO(path=self.nwb_folder_path / "test_nwb_1.nwb", mode="w") as io:
            io.write(make_nwbfile_from_metadata(metadata=metadata))

    def tearDown(self):
        rmtree(self.tmpdir)

    def test_automatic_dandi_upload(self):
        automatic_dandi_upload(dandiset_id="200560", nwb_folder_path=self.nwb_folder_path, staging=True)


@unittest.skipIf(
    not (HAVE_GLOBUS and LOGGED_INTO_GLOBUS),
    reason="You must have globus installed and be logged in to run this test!",
)
class TestGlobusTransferContent(TestCase):
    def setUp(self):
        self.tmpdir = Path(mkdtemp())  # Globus has permission issues here apparently
        self.tmpdir = Path("C:/Users/Raven/Documents/test_globus")  # For local test, which is currently the only way...

    def tearDown(self):
        rmtree(self.tmpdir)

    def test_transfer_globus_content(self):
        """Test is fixed to a subpath that is somewhat unlikely to change in the future."""
        source_endpoint_id = "188a6110-96db-11eb-b7a9-f57b2d55370d"  # Buzsaki
        destination_endpoint_id = deploy_process(command="globus endpoint local-id", catch_output=True)
        test_source_files = [
            ["/PeyracheA/Mouse12/Mouse12-120815/Mouse12-120815.clu.1"],
            [f"/PeyracheA/Mouse12/Mouse12-120815/Mouse12-120815.clu.{x}" for x in range(2, 4)],
            [f"/PeyracheA/Mouse12/Mouse12-120815/Mouse12-120815.clu.{x}" for x in range(4, 6)],
        ]
        success, task_ids = transfer_globus_content(
            source_endpoint_id=source_endpoint_id,
            source_files=test_source_files,
            destination_endpoint_id=destination_endpoint_id,
            destination_folder=self.tmpdir,
            display_progress=False,
        )
        tmpdir_size = sum(f.stat().st_size for f in self.tmpdir.glob("**/*") if f.is_file())
        assert success
        assert task_ids
        assert tmpdir_size > 0


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

    def test_make_or_load_nwbfile_write(self):
        nwbfile_path = self.tmpdir / "test_make_or_load_nwbfile_write.nwb"
        with make_or_load_nwbfile(nwbfile_path=nwbfile_path, metadata=self.metadata, overwrite=True) as nwbfile:
            nwbfile.add_acquisition(self.time_series_1)
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
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

    def test_make_or_load_nwbfile_overwrite(self):
        nwbfile_path = self.tmpdir / "test_make_or_load_nwbfile_overwrite.nwb"
        with make_or_load_nwbfile(nwbfile_path=nwbfile_path, metadata=self.metadata, overwrite=True) as nwbfile:
            nwbfile.add_acquisition(self.time_series_1)
        with make_or_load_nwbfile(nwbfile_path=nwbfile_path, metadata=self.metadata, overwrite=True) as nwbfile:
            nwbfile.add_acquisition(self.time_series_2)
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile_out = io.read()
            assert "test1" not in nwbfile_out.acquisition
            assert "test2" in nwbfile_out.acquisition

    def test_make_or_load_nwbfile_append(self):
        nwbfile_path = self.tmpdir / "test_make_or_load_nwbfile_append.nwb"
        with make_or_load_nwbfile(nwbfile_path=nwbfile_path, metadata=self.metadata, overwrite=True) as nwbfile:
            nwbfile.add_acquisition(self.time_series_1)
        with make_or_load_nwbfile(nwbfile_path=nwbfile_path) as nwbfile:
            nwbfile.add_acquisition(self.time_series_2)
        with NWBHDF5IO(path=nwbfile_path, mode="r") as io:
            nwbfile_out = io.read()
            assert "test1" in nwbfile_out.acquisition
            assert "test2" in nwbfile_out.acquisition

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
