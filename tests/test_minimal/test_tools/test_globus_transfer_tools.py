import os
import unittest
from tempfile import mkdtemp
from pathlib import Path
from shutil import rmtree

import pytest
from hdmf.testing import TestCase

from neuroconv.tools.data_transfers import (
    get_globus_dataset_content_sizes,
    estimate_s3_conversion_cost,
    estimate_total_conversion_runtime,
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
DANDI_API_KEY = os.getenv("DANDI_API_KEY")
HAVE_DANDI_KEY = DANDI_API_KEY is not None and DANDI_API_KEY != ""  # can be "" from external forks


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
    not (HAVE_GLOBUS and LOGGED_INTO_GLOBUS),
    reason="You must have globus installed and be logged in to run this test!",
)
class TestGlobusTransferContent(TestCase):
    def setUp(self):
        self.tmpdir = Path(mkdtemp())  # Globus has permission issues here apparently
        self.tmpdir = Path("C:/Users/Raven/Documents/test_globus")  # For local test, which is currently the only way...

    def tearDown(self):
        rmtree(self.tmpdir)

    @unittest.skipIf(
        not (HAVE_GLOBUS and LOGGED_INTO_GLOBUS),
        reason="You must have globus installed and be logged in to run this test!",
    )
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
