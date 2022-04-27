import os
from datetime import datetime

import pytest
from pynwb.base import ProcessingModule
from hdmf.testing import TestCase

from nwb_conversion_tools.tools.nwb_helpers import get_module, make_nwbfile_from_metadata
from nwb_conversion_tools.tools.data_transfers import get_globus_dataset_content_sizes, get_s3_conversion_cost

try:
    import globus_cli

    HAVE_GLOBUS, LOGGED_INTO_GLOBUS = True, True
    if not os.popen("globus ls 188a6110-96db-11eb-b7a9-f57b2d55370d").read():
        LOGGED_INTO_GLOBUS = False
except ModuleNotFoundError:
    HAVE_GLOBUS, LOGGED_INTO_GLOBUS = False, False


class TestConversionTools(TestCase):
    def test_get_module(self):
        nwbfile = make_nwbfile_from_metadata(
            metadata=dict(NWBFile=dict(session_start_time=datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S"))),
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
    not HAVE_GLOBUS or not LOGGED_INTO_GLOBUS,
    reason="You must have globus installed and be logged in to run this test!",
)
def test_get_globus_dataset_content_sizes():
    """Test is fixed to a subpath that is somewhat unlikely to change in the future."""
    globus_cli.login_manager.LoginManager._TEST_MODE = True
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


def test_get_s3_conversion_cost_standard():
    test_sizes = [
        1,
        100,
        1e3,  # 1 GB
        1e5,  # 100 GB
        1e6,  # 1 TB
        1e7,  # 10 TB
        1e8,  # 100 TB
    ]
    results = [get_s3_conversion_cost(total_mb=total_mb) for total_mb in test_sizes]
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
def test_get_s3_conversion_cost_from_globus():
    content_sizes = get_globus_dataset_content_sizes(
        globus_endpoint_id="188a6110-96db-11eb-b7a9-f57b2d55370d",
        path="/SenzaiY/YutaMouse41/YutaMouse41-150821/originalClu/",
    )
    assert get_s3_conversion_cost(total_mb=sum(content_sizes.values()) / 1e6) == 1.756555806400279e-13
