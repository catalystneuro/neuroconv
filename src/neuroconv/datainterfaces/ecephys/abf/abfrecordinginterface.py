"""Data interface for Axon ABF extracellular recording files."""

from pathlib import Path
from typing import List, Optional, Union

import numpy as np
from neo import AxonIO
from pydantic import FilePath, validate_call
from spikeinterface.core import BaseRecording, BaseRecordingSegment

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import get_json_schema_from_method_signature


class _AbfRecordingExtractor(BaseRecording):
    """
    Private recording extractor for ABF files using Neo's AxonIO.

    This extractor reads ABF files as extracellular electrophysiology data
    suitable for multi-electrode array recordings.
    """

    extractor_name = "AbfRecordingExtractor"
    mode = "file"
    name = "abf"

    def __init__(
        self,
        file_path: Union[str, Path],
        stream_id: Optional[str] = None,
        block_index: Optional[int] = None,
        all_annotations: bool = False,
    ):
        """
        Initialize ABF recording extractor.

        Parameters
        ----------
        file_path : str or Path
            Path to the ABF file
        stream_id : str, optional
            Stream identifier
        block_index : int, optional
            Block index to load (default: 0)
        all_annotations : bool, optional
            Whether to load all annotations (default: False)
        """
        file_path = Path(file_path)
        self.file_path = file_path
        self.stream_id = stream_id
        self.block_index = block_index or 0

        # Initialize Neo AxonIO
        self.neo_reader = AxonIO(filename=str(file_path))

        # Read the data structure
        self._read_neo_block()

        # Initialize parent class
        BaseRecording.__init__(
            self,
            sampling_frequency=self._sampling_frequency,
            channel_ids=self._channel_ids,
            dtype=self._dtype,
        )

        # Set up segments
        for segment_index in range(self._num_segments):
            segment = _AbfRecordingSegment(
                neo_reader=self.neo_reader,
                block_index=self.block_index,
                segment_index=segment_index,
                stream_id=self.stream_id,
            )
            self.add_recording_segment(segment)

        # Add annotations if requested
        if all_annotations:
            self._add_neo_annotations()

    def _read_neo_block(self):
        """Read the Neo block and extract basic information."""
        # Read the block
        block = self.neo_reader.read_block(
            block_index=self.block_index,
            lazy=True,
        )

        # Get analog signals from the first segment
        if not block.segments:
            raise ValueError(f"No segments found in ABF file {self.file_path}")

        segment = block.segments[0]
        if not segment.analogsignals:
            raise ValueError(f"No analog signals found in ABF file {self.file_path}")

        # Use the first analog signal to get metadata
        analog_signal = segment.analogsignals[0]

        # Extract basic properties
        self._sampling_frequency = float(analog_signal.sampling_rate.magnitude)
        self._num_channels = int(analog_signal.shape[1])
        self._channel_ids = [f"ch{i}" for i in range(self._num_channels)]
        self._dtype = analog_signal.dtype
        self._num_segments = len(block.segments)

        # Store units information
        if hasattr(analog_signal, "units"):
            self._units = str(analog_signal.units)
        else:
            self._units = "uV"  # Default unit

    def _add_neo_annotations(self):
        """Add Neo annotations to the extractor."""
        try:
            block = self.neo_reader.read_block(
                block_index=self.block_index,
                lazy=True,
            )

            # Add block-level annotations
            if hasattr(block, "annotations") and block.annotations:
                for key, value in block.annotations.items():
                    if isinstance(value, (str, int, float, bool)):
                        self.set_annotation(key, value)
        except Exception:
            # If annotations fail, continue without them
            pass


class _AbfRecordingSegment(BaseRecordingSegment):
    """
    Recording segment for ABF files.
    """

    def __init__(
        self,
        neo_reader: AxonIO,
        block_index: int,
        segment_index: int,
        stream_id: Optional[str] = None,
    ):
        """
        Initialize ABF recording segment.

        Parameters
        ----------
        neo_reader : AxonIO
            Neo AxonIO reader instance
        block_index : int
            Block index
        segment_index : int
            Segment index
        stream_id : str, optional
            Stream identifier
        """
        self.neo_reader = neo_reader
        self.block_index = block_index
        self.segment_index = segment_index
        self.stream_id = stream_id

        # Read segment to get sample count
        self._read_segment_info()

        BaseRecordingSegment.__init__(
            self,
            sampling_frequency=self._sampling_frequency,
        )

    def _read_segment_info(self):
        """Read segment information to determine sample count."""
        # Read the specific segment
        block = self.neo_reader.read_block(
            block_index=self.block_index,
            lazy=True,
        )

        segment = block.segments[self.segment_index]
        if not segment.analogsignals:
            raise ValueError(f"No analog signals in segment {self.segment_index}")

        analog_signal = segment.analogsignals[0]
        self._num_samples = int(analog_signal.shape[0])
        self._sampling_frequency = float(analog_signal.sampling_rate.magnitude)

    def get_num_samples(self) -> int:
        """Get the number of samples in this segment."""
        return self._num_samples

    def get_traces(
        self,
        start_frame: Optional[int] = None,
        end_frame: Optional[int] = None,
        channel_indices: Optional[List[int]] = None,
    ) -> np.ndarray:
        """
        Get trace data from the ABF file.

        Parameters
        ----------
        start_frame : int, optional
            Start frame (default: 0)
        end_frame : int, optional
            End frame (default: num_samples)
        channel_indices : list of int, optional
            Channel indices to load (default: all channels)

        Returns
        -------
        np.ndarray
            Trace data with shape (num_samples, num_channels)
        """
        # Set defaults
        start_frame = start_frame if start_frame is not None else 0
        end_frame = end_frame if end_frame is not None else self._num_samples

        # Read the segment data (not lazy this time)
        block = self.neo_reader.read_block(
            block_index=self.block_index,
            lazy=False,
        )

        segment = block.segments[self.segment_index]
        analog_signal = segment.analogsignals[0]

        # Extract data as numpy array
        traces = np.array(analog_signal.magnitude, dtype=analog_signal.dtype)

        # Slice time dimension
        traces = traces[start_frame:end_frame, :]

        # Select channels if specified
        if channel_indices is not None:
            traces = traces[:, channel_indices]

        return traces


class AbfRecordingInterface(BaseRecordingExtractorInterface):
    """
    Data interface for ABF extracellular recording files.

    This interface treats ABF files as extracellular electrophysiology
    recording data, suitable for multi-electrode array recordings.
    For intracellular data, use the AbfInterface instead.
    """

    display_name = "ABF Recording"
    keywords = BaseRecordingExtractorInterface.keywords + ("axon", "abf")
    associated_suffixes = (".abf",)
    info = "Interface for ABF extracellular recording data from Axon instruments."

    # Use our private ABF extractor
    ExtractorName = "_AbfRecordingExtractor"

    @classmethod
    def get_extractor(cls):
        """Return the private ABF extractor class."""
        return _AbfRecordingExtractor

    @classmethod
    def get_source_schema(cls) -> dict:
        """Get the schema for the source data."""
        source_schema = get_json_schema_from_method_signature(method=cls.__init__, exclude=["stream_id", "block_index"])
        source_schema.update(additionalProperties=True)
        source_schema["properties"]["file_path"].update(description="Path to ABF file.")
        return source_schema

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        stream_id: str | None = None,
        block_index: int | None = None,
        verbose: bool = False,
        es_key: str = "ElectricalSeries",
    ):
        """
        Initialize reading of ABF file as extracellular recording data.

        Parameters
        ----------
        file_path : FilePath
            Path to ABF file.
        stream_id : str, optional
            If there are several streams, specify the stream id you want to load.
        block_index : int, optional
            If there are several blocks, specify the block index you want to load.
        verbose : bool, default: False
            If True, will print out additional information.
        es_key : str, default: "ElectricalSeries"
            The key of this ElectricalSeries in the metadata dictionary.
        """
        # Use our private ABF extractor
        super().__init__(
            file_path=file_path,
            stream_id=stream_id,
            block_index=block_index,
            verbose=verbose,
            es_key=es_key,
        )

    def _source_data_to_extractor_kwargs(self, source_data: dict) -> dict:
        """Convert source data to extractor kwargs."""
        extractor_kwargs = source_data.copy()
        extractor_kwargs["all_annotations"] = True
        return extractor_kwargs
