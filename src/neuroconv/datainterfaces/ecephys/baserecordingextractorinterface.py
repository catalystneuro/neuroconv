"""Authors: Cody Baker and Ben Dichter."""
from typing import Optional
from warnings import warn

from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ecephys import ElectrodeGroup

from ...baseextractorinterface import BaseExtractorInterface
from ...utils import get_schema_from_hdmf_class, get_base_schema, OptionalFilePathType, format_docstring
from ...docstrings import compression_options_docstring, iterator_options_docstring


class BaseRecordingExtractorInterface(BaseExtractorInterface):
    """Parent class for all RecordingExtractorInterfaces."""

    ExtractorModuleName: Optional[str] = "spikeinterface.extractors"

    def __init__(self, verbose: bool = True, **source_data):
        """
        Parameters
        ----------
        verbose : bool, default True
            If True, will print out additional information.
        source_data : dict
            key-value pairs of extractor-specific arguments.

        """
        super().__init__(**source_data)
        self.recording_extractor = self.Extractor(**source_data)
        self.subset_channels = None
        self.verbose = verbose
        self.es_key = None  # For automatic metadata extraction

    def get_metadata_schema(self):
        """Compile metadata schema for the RecordingExtractor."""
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"] = get_base_schema(tag="Ecephys")
        metadata_schema["properties"]["Ecephys"]["required"] = ["Device", "ElectrodeGroup"]
        metadata_schema["properties"]["Ecephys"]["properties"] = dict(
            Device=dict(type="array", minItems=1, items={"$ref": "#/properties/Ecephys/properties/definitions/Device"}),
            ElectrodeGroup=dict(
                type="array", minItems=1, items={"$ref": "#/properties/Ecephys/properties/definitions/ElectrodeGroup"}
            ),
            Electrodes=dict(
                type="array",
                minItems=0,
                renderForm=False,
                items={"$ref": "#/properties/Ecephys/properties/definitions/Electrodes"},
            ),
        )
        # Schema definition for arrays
        metadata_schema["properties"]["Ecephys"]["properties"]["definitions"] = dict(
            Device=get_schema_from_hdmf_class(Device),
            ElectrodeGroup=get_schema_from_hdmf_class(ElectrodeGroup),
            Electrodes=dict(
                type="object",
                additionalProperties=False,
                required=["name"],
                properties=dict(
                    name=dict(type="string", description="name of this electrodes column"),
                    description=dict(type="string", description="description of this electrodes column"),
                ),
            ),
        )
        return metadata_schema

    def get_metadata(self):
        metadata = super().get_metadata()

        channel_groups_array = self.recording_extractor.get_channel_groups()
        unique_channel_groups = set(channel_groups_array) if channel_groups_array is not None else ["ElectrodeGroup"]
        electrode_metadata = [
            dict(name=str(group_id), description="no description", location="unknown", device="DeviceEcephys")
            for group_id in unique_channel_groups
        ]

        metadata["Ecephys"] = dict(
            Device=[dict(name="DeviceEcephys", description="no description")],
            ElectrodeGroup=electrode_metadata,
        )

        return metadata

    def subset_recording(self, stub_test: bool = False):
        """
        Subset a recording extractor according to stub and channel subset options.

        Parameters
        ----------
        stub_test : bool, optional, default False
        """
        from spikeextractors import RecordingExtractor, SubRecordingExtractor
        from spikeinterface import BaseRecording

        kwargs = dict()
        if stub_test:
            num_frames = 100
            end_frame = min([num_frames, self.recording_extractor.get_num_frames()])
            kwargs.update(end_frame=end_frame)
        if self.subset_channels is not None:
            kwargs.update(channel_ids=self.subset_channels)
        if isinstance(self.recording_extractor, RecordingExtractor):
            recording_extractor = SubRecordingExtractor(self.recording_extractor, **kwargs)
        elif isinstance(self.recording_extractor, BaseRecording):
            recording_extractor = self.recording_extractor.frame_slice(start_frame=0, end_frame=end_frame)
        else:
            raise TypeError(f"{self.recording_extractor} should be either se.RecordingExtractor or si.BaseRecording")
        return recording_extractor

    def run_conversion(
        self,
        nwbfile_path: OptionalFilePathType = None,
        nwbfile: Optional[NWBFile] = None,
        metadata: Optional[dict] = None,
        overwrite: bool = False,
        stub_test: bool = False,
        starting_time: Optional[float] = None,
        use_times: bool = False,  # To-do to remove, deprecation
        write_as: Optional[str] = None,
        write_electrical_series: bool = True,
        es_key: str = None,
        compression_options: Optional[dict] = None,
        iterator_options: Optional[dict] = None,
        compression: Optional[str] = None,  # TODO: remove
        compression_opts: Optional[int] = None,  # TODO: remove
        iterator_type: Optional[str] = None,  # TODO: remove
        iterator_opts: Optional[dict] = None,  # TODO: remove
    ):
        """
        Primary function for converting raw (unprocessed) RecordingExtractor data to the NWB standard.

        Parameters
        ----------
        nwbfile_path : FilePathType
            Path for where to write or load (if overwrite=False) the NWBFile.
            If specified, this context will always write to this location.
        nwbfile : NWBFile, optional
            NWBFile to which the recording information is to be added
        metadata : dict, optional
            metadata info for constructing the NWB file.
            Should be of the format::

                metadata['Ecephys']['ElectricalSeries'] = dict(name=my_name, description=my_description)
        overwrite: bool, optional
            Whether or not to overwrite the NWB file if one exists at the nwbfile_path.
        The default is False (append mode).
        starting_time : float, optional
            Sets the starting time of the ElectricalSeries to a manually set value.
            Increments timestamps if use_times is True.
        stub_test : bool, optional, default False
            If True, will truncate the data to run the conversion faster and take up less memory.
        write_as : {'raw', 'lfp', 'processed'}
        write_electrical_series : bool, default: True
            Electrical series are written in acquisition. If False, only device, electrode_groups,
            and electrodes are written to NWB.
        es_key : str, optional
            Key in metadata dictionary containing metadata info for the specific electrical series
        {compression_options_docstring}
        {iterator_options_docstring}
        """
        if any([x is not None for x in [compression, compression_opts]]):  # pragma: no cover
            assert compression_options is None, (
                "You may not specify both 'compression' and 'compression_opts' with 'compression_options'! "
                "Please use only 'compression_options'."
            )
            warn(
                message=(
                    "The options 'compression' and 'compression_opts' will soon be deprecated! "
                    "Please use 'compression_options' instead."
                ),
                category=DeprecationWarning,
                stacklevel=2,
            )
            compression_options = dict(
                method=compression if isinstance(compression, str) else "gzip",
                method_options=compression_opts,
            )
        if any([x is not None for x in [iterator_type, iterator_opts]]):  # pragma: no cover
            assert iterator_options is None, (
                "You may not specify both 'iterator_type' and 'iterator_opts' with 'iterator_options'! "
                "Please use only 'iterator_options'."
            )
            warn(
                message=(
                    "The options 'iterator_type' and 'iterator_opts' will soon be deprecated! "
                    "Please use 'iterator_options' instead."
                ),
                category=DeprecationWarning,
                stacklevel=2,
            )
            iterator_options = dict(
                method=iterator_type or "v2",
                method_options=iterator_opts or dict(),
            )

        from ...tools.spikeinterface import write_recording

        compression_options = compression_options or dict(method="gzip")
        iterator_options = iterator_options or dict(method="v2")

        if stub_test or self.subset_channels is not None:
            recording = self.subset_recording(stub_test=stub_test)
        else:
            recording = self.recording_extractor

        write_recording(
            recording=recording,
            nwbfile_path=nwbfile_path,
            nwbfile=nwbfile,
            metadata=metadata,
            overwrite=overwrite,
            verbose=self.verbose,
            starting_time=starting_time,
            use_times=use_times,
            write_as=write_as,
            write_electrical_series=write_electrical_series,
            es_key=es_key or self.es_key,
            compression_options=compression_options,
            iterator_options=iterator_options,
        )


format_docstring(
    function=BaseRecordingExtractorInterface.run_conversion,
    tab_level=2,
    compression_options_docstring=compression_options_docstring,
    iterator_options_docstring=iterator_options_docstring,
)
