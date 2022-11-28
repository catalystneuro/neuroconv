from datetime import datetime
from typing import Optional

from pynwb import NWBFile
from pynwb.testing.mock.file import mock_NWBFile
from pynwb.testing.mock.base import mock_TimeSeries

from ..nwb_helpers import make_or_load_nwbfile
from ...basedatainterface import BaseDataInterface


class MockDataInterface(BaseDataInterface):
    def get_metadata(self):
        metadata = super().get_metadata()

        timestamp = datetime(year=2022, month=11, day=28, hour=13, minute=20, second=23)
        self.set_start_time(timestamp=timestamp)
        metadata["NWBFile"].update(session_start_time=timestamp)

        return metadata

    def run_conversion(
        self,
        nwbfile_path: Optional[str] = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
    ):
        nwbfile = mock_NWBFile()
        with make_or_load_nwbfile(
            nwbfile_path=nwbfile_path, nwbfile=nwbfile, metadata=metadata, overwrite=overwrite
        ) as nwbfile:
            nwbfile.add_acquisition(mock_TimeSeries())
