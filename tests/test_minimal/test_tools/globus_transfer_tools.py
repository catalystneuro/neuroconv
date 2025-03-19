import importlib
import os
import unittest
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp

import pytest
from hdmf.testing import TestCase

from neuroconv.tools import deploy_process
from neuroconv.tools.data_transfers import (
    get_globus_dataset_content_sizes,
    transfer_globus_content,
)

HAVE_GLOBUS = importlib.util.find_spec(name="globus_cli") is None
LOGGED_INTO_GLOBUS = os.popen("globus ls 188a6110-96db-11eb-b7a9-f57b2d55370d").read()

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
