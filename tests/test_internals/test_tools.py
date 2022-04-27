from datetime import datetime

from pynwb.base import ProcessingModule
from hdmf.testing import TestCase

from nwb_conversion_tools.tools.nwb_helpers import get_module, make_nwbfile_from_metadata
from nwb_conversion_tools.tools.data_transfers import get_globus_dataset_content_sizes, get_s3_conversion_cost


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


def test_get_s3_conversion_cost():
    content_sizes = get_globus_dataset_content_sizes(
        globus_endpoint_id="188a6110-96db-11eb-b7a9-f57b2d55370d",
        path="/SenzaiY/YutaMouse41/YutaMouse41-150821/originalClu/",
    )
    assert get_s3_conversion_cost(total_mb=sum(content_sizes.values()) / 1e6) == 1.756555806400279e-13
