from spikeinterface.extractors import MaxwellRecordingExtractor

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface


class MaxwellRecordingInterface(BaseRecordingExtractorInterface):

    RX = MaxwellRecordingExtractor

    def __init__(self, file_path, stream_id=None, rec_name=None, verbose=False):
        """
        Convert Maxwell data to NWB

        Parameters
        ----------
        file_path: str
            Path to maxwell h5 file
        stream_id: str or None
            For MaxTwo when there are several wells at the same time you
            need to specify stream_id='well000' or 'well0001' or ...
        rec_name: str or None
            When the file contains several blocks (aka recordings) you need to specify the one
            you want to extract. (rec_name='rec0000')
        """
        super().__init__(verbose=verbose, file_path=file_path, stream_id=stream_id, rec_name=rec_name)
