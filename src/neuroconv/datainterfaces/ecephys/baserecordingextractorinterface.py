import warnings
from typing import Literal

import numpy as np
from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ecephys import ElectricalSeries, ElectrodeGroup

from ...baseextractorinterface import BaseExtractorInterface
from ...utils import (
    DeepDict,
    get_base_schema,
    get_schema_from_hdmf_class,
)


class BaseRecordingExtractorInterface(BaseExtractorInterface):
    """Parent class for all RecordingExtractorInterfaces."""

    keywords = ("extracellular electrophysiology", "voltage", "recording")

    def _initialize_extractor(self, interface_kwargs: dict):
        """
        Initialize and return the extractor instance for recording interfaces.

        Extends the base implementation to also remove the 'es_key' parameter
        which is specific to the recording interface, not the extractor.
        Also adds 'all_annotations=True' to ensure all metadata is loaded.

        Parameters
        ----------
        interface_kwargs : dict
            The source data parameters passed to the interface constructor.

        Returns
        -------
        extractor_instance
            An initialized recording extractor instance.
        """
        self.extractor_kwargs = interface_kwargs.copy()
        self.extractor_kwargs.pop("verbose", None)
        self.extractor_kwargs.pop("es_key", None)
        self.extractor_kwargs.pop("metadata_key", None)
        self.extractor_kwargs["all_annotations"] = True

        extractor_class = self.get_extractor_class()
        extractor_instance = extractor_class(**self.extractor_kwargs)
        return extractor_instance

    def __init__(
        self,
        verbose: bool = False,
        es_key: str = "ElectricalSeries",
        *,
        metadata_key: str | None = None,
        **source_data,
    ):
        """
        Parameters
        ----------
        verbose : bool, default: False
            If True, will print out additional information.
        es_key : str, default: "ElectricalSeries"
            The key of this ElectricalSeries in the metadata dictionary.
        metadata_key : str, optional
            Key of this interface's ElectricalSeries in the dict-based metadata format.
            Defaults to the value of ``es_key``.
        source_data : dict
            The key-value pairs of extractor-specific arguments.

        """

        super().__init__(**source_data)
        self.recording_extractor = self._extractor_instance
        property_names = self.recording_extractor.get_property_keys()
        # TODO remove this and go and change all the uses of channel_name once spikeinterface > 0.101.0 is released
        if "channel_name" not in property_names and "channel_names" in property_names:
            channel_names = self.recording_extractor.get_property("channel_names")
            self.recording_extractor.set_property("channel_name", channel_names)
            self.recording_extractor.delete_property("channel_names")

        self.verbose = verbose
        self.es_key = es_key
        self.metadata_key = metadata_key if metadata_key is not None else es_key
        self._number_of_segments = self.recording_extractor.get_num_segments()

    def get_metadata_schema(self) -> dict:
        """
        Compile the metadata schema.

        The registries are objects keyed by ``metadata_key``, and the entries stay permissive: an entry is
        passed to a pynwb constructor, so it may legitimately carry any field that constructor takes. What is
        pinned is the shape, that an entry is an object, which is also what catches an edit written against
        the old format landing in a block that exists in both
        (``metadata["Ecephys"]["ElectricalSeries"]["name"] = ...``).

        Metadata in the old list-based format is validated against
        ``_get_metadata_schema_for_old_list_format``, and both go when that format does.
        """
        from ...basedatainterface import BaseDataInterface

        metadata_schema = BaseDataInterface.get_metadata_schema(self)
        metadata_schema["properties"]["Ecephys"] = get_base_schema(tag="Ecephys")
        metadata_schema["properties"]["Ecephys"]["required"] = []
        metadata_schema["properties"]["Ecephys"]["properties"] = dict(
            ElectrodeGroups=dict(
                type="object",
                additionalProperties={"$ref": "#/properties/Ecephys/definitions/ElectrodeGroupEntry"},
            ),
            ElectricalSeries=dict(
                type="object",
                additionalProperties={"$ref": "#/properties/Ecephys/definitions/ElectricalSeriesEntry"},
            ),
            # The electrode table's column descriptions are still a list in both formats.
            Electrodes=dict(
                type="array",
                minItems=0,
                renderForm=False,
                items={"$ref": "#/properties/Ecephys/definitions/Electrodes"},
            ),
        )
        metadata_schema["properties"]["Ecephys"]["definitions"] = dict(
            ElectrodeGroupEntry=dict(
                type="object",
                additionalProperties=True,
                properties=dict(
                    name=dict(type="string", pattern="^[^/]*$"),
                    description=dict(type="string"),
                    location=dict(type="string"),
                    device_metadata_key=dict(
                        type="string",
                        description="Key of this group's device in metadata['Devices'].",
                    ),
                ),
            ),
            ElectricalSeriesEntry=dict(
                type="object",
                additionalProperties=True,
                properties=dict(
                    name=dict(type="string", pattern="^[^/]*$"),
                    description=dict(type="string"),
                ),
            ),
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

    def _get_metadata_schema_for_old_list_format(self) -> dict:
        """
        Compile metadata schema for the RecordingExtractor.

        Returns
        -------
        dict
            The metadata schema dictionary containing definitions for Device, ElectrodeGroup,
            Electrodes, and optionally ElectricalSeries.
        """
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"] = get_base_schema(tag="Ecephys")
        metadata_schema["properties"]["Ecephys"]["required"] = ["Device", "ElectrodeGroup"]
        metadata_schema["properties"]["Ecephys"]["properties"] = dict(
            Device=dict(type="array", minItems=1, items={"$ref": "#/properties/Ecephys/definitions/Device"}),
            ElectrodeGroup=dict(
                type="array", minItems=1, items={"$ref": "#/properties/Ecephys/definitions/ElectrodeGroup"}
            ),
            Electrodes=dict(
                type="array",
                minItems=0,
                renderForm=False,
                items={"$ref": "#/properties/Ecephys/definitions/Electrodes"},
            ),
        )
        # Schema definition for arrays
        metadata_schema["properties"]["Ecephys"]["definitions"] = dict(
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

        if self.es_key is not None:
            metadata_schema["properties"]["Ecephys"]["properties"].update(
                {self.es_key: get_schema_from_hdmf_class(ElectricalSeries)}
            )
        return metadata_schema

    def get_metadata(self, *, use_new_metadata_format: bool = True) -> DeepDict:
        metadata = super().get_metadata()

        if use_new_metadata_format:
            # Dict-based format: emit only the ElectricalSeries entry keyed by ``metadata_key`` (which
            # also marks the metadata as dict-based, so the pipeline dispatches to the new path). The
            # default device and electrode groups are left to the pipeline, which creates a default
            # device and synthesizes one group per channel-group from the recording's ``group`` properties.
            # The name is the NWB-conventional default, independent of ``es_key`` (legacy, to be removed) and
            # of ``metadata_key`` (the dict key). No description: a generic one carries no information, so it
            # is left to the interfaces, which can say something the source actually supports, and otherwise
            # to the write pipeline.
            metadata["Ecephys"] = {"ElectricalSeries": {self.metadata_key: dict(name="ElectricalSeries")}}

            return metadata

        from ...tools.spikeinterface.spikeinterface import _get_group_name

        channel_groups_array = _get_group_name(recording=self.recording_extractor)
        unique_channel_groups = set(channel_groups_array) if channel_groups_array is not None else ["ElectrodeGroup"]
        electrode_metadata = [
            dict(name=str(group_id), description="no description", location="unknown", device="DeviceEcephys")
            for group_id in unique_channel_groups
        ]

        metadata["Ecephys"] = dict(
            Device=[dict(name="DeviceEcephys", description="no description")],
            ElectrodeGroup=electrode_metadata,
        )

        if self.es_key is not None:
            metadata["Ecephys"][self.es_key] = dict(
                name=self.es_key, description=f"Acquisition traces for the {self.es_key}."
            )

        return metadata

    @property
    def channel_ids(self):
        "Gets the channel ids of the data."
        return self.recording_extractor.get_channel_ids()

    def remove_channels(self, channel_ids: list):
        """
        Drop the given channels from the recording held by this interface.

        Parameters
        ----------
        channel_ids : list
            The ids of the channels to drop, as returned by the ``channel_ids`` property.

        Returns
        -------
        BaseRecordingExtractorInterface
            This interface, so the call can be chained.
        """
        self.recording_extractor = self.recording_extractor.remove_channels(remove_channel_ids=channel_ids)
        return self

    def get_original_timestamps(self) -> np.ndarray | list[np.ndarray]:
        """
        Retrieve the original unaltered timestamps for the data in this interface.

        This function should retrieve the data on-demand by re-initializing the IO.

        Returns
        -------
        timestamps: numpy.ndarray or list of numpy.ndarray
            The timestamps for the data stream; if the recording has multiple segments, then a list of timestamps is returned.
        """
        new_recording = self._initialize_extractor(self.source_data)

        if self._number_of_segments == 1:
            return new_recording.get_times()
        else:
            return [
                new_recording.get_times(segment_index=segment_index)
                for segment_index in range(self._number_of_segments)
            ]

    def get_timestamps(self) -> np.ndarray | list[np.ndarray]:
        """
        Retrieve the timestamps for the data in this interface.

        Returns
        -------
        timestamps: numpy.ndarray or list of numpy.ndarray
            The timestamps for the data stream; if the recording has multiple segments, then a list of timestamps is returned.
        """
        if self._number_of_segments == 1:
            return self.recording_extractor.get_times()
        else:
            return [
                self.recording_extractor.get_times(segment_index=segment_index)
                for segment_index in range(self._number_of_segments)
            ]

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray):
        assert (
            self._number_of_segments == 1
        ), "This recording has multiple segments; please use 'align_segment_timestamps' instead."

        self.recording_extractor.set_times(times=aligned_timestamps, with_warning=False)

    def set_aligned_segment_timestamps(self, aligned_segment_timestamps: list[np.ndarray]):
        """
        Replace all timestamps for all segments in this interface with those aligned to the common session start time.

        Must be in units seconds relative to the common 'session_start_time'.

        Parameters
        ----------
        aligned_segment_timestamps : list of numpy.ndarray
            The synchronized timestamps for segment of data in this interface.
        """
        assert isinstance(
            aligned_segment_timestamps, list
        ), "Recording has multiple segment! Please pass a list of timestamps to align each segment."
        assert (
            len(aligned_segment_timestamps) == self._number_of_segments
        ), f"The number of timestamp vectors ({len(aligned_segment_timestamps)}) does not match the number of segments ({self._number_of_segments})!"

        for segment_index in range(self._number_of_segments):
            self.recording_extractor.set_times(
                times=aligned_segment_timestamps[segment_index],
                segment_index=segment_index,
                with_warning=False,
            )

    def set_aligned_starting_time(self, aligned_starting_time: float):
        if self._number_of_segments == 1:
            self.set_aligned_timestamps(aligned_timestamps=self.get_timestamps() + aligned_starting_time)
        else:
            self.set_aligned_segment_timestamps(
                aligned_segment_timestamps=[
                    segment_timestamps + aligned_starting_time for segment_timestamps in self.get_timestamps()
                ]
            )

    def set_aligned_segment_starting_times(self, aligned_segment_starting_times: list[float]):
        """
        Align the starting time for each segment in this interface relative to the common session start time.

        Must be in units seconds relative to the common 'session_start_time'.

        Parameters
        ----------
        aligned_segment_starting_times : list of floats
            The starting time for each segment of data in this interface.
        """
        assert len(aligned_segment_starting_times) == self._number_of_segments, (
            f"The length of the starting_times ({len(aligned_segment_starting_times)}) does not match the "
            "number of segments ({self._number_of_segments})!"
        )

        if self._number_of_segments == 1:
            self.set_aligned_starting_time(aligned_starting_time=aligned_segment_starting_times[0])
        else:
            aligned_segment_timestamps = [
                segment_timestamps + aligned_segment_starting_time
                for segment_timestamps, aligned_segment_starting_time in zip(
                    self.get_timestamps(), aligned_segment_starting_times
                )
            ]
            self.set_aligned_segment_timestamps(aligned_segment_timestamps=aligned_segment_timestamps)

    def set_probe(self, probe: "Probe | ProbeGroup", group_mode: Literal["by_shank", "by_probe"]):
        """
        Set the probe information via a ProbeInterface object.

        Parameters
        ----------
        probe : probeinterface.Probe or probeinterface.ProbeGroup
            The probe object(s). Can be a single Probe or a ProbeGroup containing multiple probes.
        group_mode : {'by_shank', 'by_probe'}
            How to group the channels for electrode group assignment in the NWB file:

            - 'by_probe': Each probe becomes a separate electrode group. For a ProbeGroup with
            multiple probes, each probe gets its own group (group 0, 1, 2, etc.). For a single
            probe, all channels are assigned to group 0.

            - 'by_shank': Each unique combination of probe and shank becomes a separate electrode
            group. Requires that shank_ids are defined for all probes. Groups are assigned
            sequentially for each unique (probe_index, shank_id) pair.

            The resulting groups determine how electrode groups and electrodes are organized
            in the NWB file, with each group corresponding to one ElectrodeGroup.
        """
        from probeinterface import ProbeGroup

        # Set the probe to the recording extractor. SpikeInterface 0.105 removed the private
        # `_set_probes`, which took either a Probe or a ProbeGroup; the public entry points are split
        # by type, so dispatch here.
        # TODO: drop `in_place=True` once spikeinterface>=0.105.0 is the minimum pin, where these calls
        # are always in place and the argument is deprecated. It is required on 0.104, which otherwise
        # returns a new recording and leaves this one unchanged.
        if isinstance(probe, ProbeGroup):
            self.recording_extractor.set_probegroup(probe, group_mode=group_mode, in_place=True)
        else:
            self.recording_extractor.set_probe(probe, group_mode=group_mode, in_place=True)

        # Spike interface sets the "group" property
        # But neuroconv allows "group_name" property to override spike interface "group" value
        # So we re-set this here to avoid a conflict
        self.recording_extractor.set_property("group_name", self.recording_extractor.get_property("group").astype(str))

    def has_probe(self) -> bool:
        """
        Check if the recording extractor has probe information.

        Returns
        -------
        bool
            True if the recording extractor has probe information, False otherwise.
        """
        return self.recording_extractor.has_probe()

    def align_by_interpolation(
        self,
        unaligned_timestamps: np.ndarray,
        aligned_timestamps: np.ndarray,
    ):
        if self._number_of_segments == 1:
            self.set_aligned_timestamps(
                aligned_timestamps=np.interp(x=self.get_timestamps(), xp=unaligned_timestamps, fp=aligned_timestamps)
            )
        else:
            raise NotImplementedError("Multi-segment support for aligning by interpolation has not been added yet.")

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *,
        stub_test: bool = False,
        parent_container: Literal["acquisition", "processing/LFP", "processing/FilteredEphys"] = "acquisition",
        write_as: Literal["raw", "lfp", "processed"] | None = None,
        data_representation: Literal["digital_counts", "physical_units"] = "digital_counts",
        write_electrical_series: bool = True,
        iterator_type: str | None = "v2",
        iterator_options: dict | None = None,
        always_write_timestamps: bool = False,
    ):
        """
        Primary function for converting raw (unprocessed) RecordingExtractor data to the NWB standard.

        Parameters
        ----------
        nwbfile : NWBFile
            NWBFile to which the recording information is to be added
        metadata : dict, optional
            metadata info for constructing the NWB file.
            Should be of the format::

                metadata['Ecephys']['ElectricalSeries'] = dict(name=my_name, description=my_description)

        stub_test : bool, default: False
            If True, will truncate the data to run the conversion faster and take up less memory.
        parent_container : {'acquisition', 'processing/LFP', 'processing/FilteredEphys'}, default: 'acquisition'
            Which NWB container to write the trace data to. Options are:
            - 'acquisition': raw acquired data, in the acquisition group.
            - 'processing/LFP': an ``LFP`` container in the ecephys processing module.
            - 'processing/FilteredEphys': a ``FilteredEphys`` container in the ecephys processing module.
        write_as : {'raw', 'processed', 'lfp'}, optional
            Deprecated. Use ``parent_container`` instead ('raw' -> 'acquisition', 'lfp' -> 'processing/LFP',
            'processed' -> 'processing/FilteredEphys'). Will be removed on or after February 2027.
        data_representation : {'digital_counts', 'physical_units'}, default='digital_counts'
            How the trace values are materialized in the stored data array.
            - 'digital_counts': store the raw integer samples and carry the per-channel gain in
              ``channel_conversion`` (or a scalar ``conversion`` when homogeneous) and the offset in
              the scalar ``offset``. Faithful and compact, but requires a common offset across channels.
            - 'physical_units': apply each channel's gain and offset and store float physical values,
              so the scalar ``offset`` is 0 and no ``channel_conversion`` is needed. This is the only
              representation that can hold channels with heterogeneous per-channel offsets (and gains)
              in a single series, at the cost of float storage and no lossless integer round-trip.

        write_electrical_series : bool, default: True
            Electrical series are written in acquisition. If False, only device, electrode_groups,
            and electrodes are written to NWB.
        iterator_type : {'v2', None}, default: 'v2'
            The type of iterator for chunked data writing.
            'v2': Uses iterative write with control over chunking and progress bars.
            None: Loads all data into memory before writing (not recommended for large datasets).
        iterator_options : dict, optional
            Options for controlling iterative write when iterator_type='v2'.
            See the `pynwb tutorial on iterative write
            <https://pynwb.readthedocs.io/en/stable/tutorials/advanced_io/plot_iterative_write.html#sphx-glr-tutorials-advanced-io-plot-iterative-write-py>`_
            for more information on chunked data writing.

            Available options:

            * buffer_gb : float, default: 1.0
                RAM to use for buffering data chunks in GB. Recommended to be as much free RAM as available.
            * buffer_shape : tuple, optional
                Manual specification of buffer shape. Must be a multiple of chunk_shape along each axis.
                Cannot be set if buffer_gb is specified.
            * display_progress : bool, default: False
                Enable tqdm progress bar during data write.
            * progress_bar_options : dict, optional
                Additional options passed to tqdm progress bar.
                See https://github.com/tqdm/tqdm#parameters for all tqdm options.

            Note: To configure chunk size and compression, use the backend configuration system
            via ``get_default_backend_configuration()`` and ``configure_backend()`` after calling
            this method. See the backend configuration documentation for details.
        always_write_timestamps : bool, default: False
            Set to True to always write timestamps.
            By default (False), the function checks if the timestamps are uniformly sampled, and if so, stores the data
            using a regular sampling rate instead of explicit timestamps. If set to True, timestamps will be written
            explicitly, regardless of whether the sampling rate is uniform.
        """
        if write_as is not None:
            warnings.warn(
                "The 'write_as' parameter of BaseRecordingExtractorInterface.add_to_nwbfile() is deprecated and "
                "will be removed on or after February 2027. Use 'parent_container' instead "
                "('raw' -> 'acquisition', 'lfp' -> 'processing/LFP', 'processed' -> 'processing/FilteredEphys').",
                FutureWarning,
                stacklevel=2,
            )
            parent_container = {"raw": "acquisition", "lfp": "processing/LFP", "processed": "processing/FilteredEphys"}[
                write_as
            ]

        from ...tools.spikeinterface import (
            _stub_recording,
            add_recording_metadata_to_nwbfile,
            add_recording_to_nwbfile,
        )

        recording = self.recording_extractor
        if stub_test:
            recording = _stub_recording(recording=recording)

        metadata = metadata or self._get_metadata_for_writing()

        # ``metadata_key`` selects the ElectricalSeries entry in the dict-based format and is mutually
        # exclusive with ``es_key`` downstream. The question is asked of this interface's own entry rather
        # than of the dictionary's overall shape: a converter can hand every interface one dictionary that
        # carries another interface's dict-based block (a video camera's ``Devices``, a NIDQ board's)
        # alongside this one's list-based ``Ecephys``, and only the presence of *this* key says which
        # format the caller means for *this* interface.
        electrical_series_metadata = metadata.get("Ecephys", {}).get("ElectricalSeries", {})
        entry_is_present = (
            isinstance(electrical_series_metadata, dict) and self.metadata_key in electrical_series_metadata
        )
        metadata_key = self.metadata_key if entry_is_present else None

        if write_electrical_series:
            if (
                data_representation != "physical_units"
                and recording.has_scaleable_traces()
                and len(set(recording.get_channel_offsets())) > 1
            ):
                from ...tools.spikeinterface.spikeinterface import (
                    _describe_offset_groups,
                )

                raise ValueError(
                    "The channels of this recording have heterogeneous offsets, which a single NWB "
                    "ElectricalSeries cannot represent.\n"
                    "Multiple offsets were found per channel IDs:\n"
                    f"{_describe_offset_groups(recording=recording)}\n"
                    "\n"
                    "If these channels are all the same kind of signal and the offsets come from "
                    "per-channel scaling, pass data_representation='physical_units' as a conversion "
                    "option to add_to_nwbfile() or run_conversion() to write them as one series (this "
                    "folds each channel's offset into the data and writes float physical values). If the "
                    "channels carrying the odd offsets are not electrode channels, drop them with "
                    "interface.remove_channels(channel_ids=[...]) and write them as TimeSeries instead. "
                    "See https://neuroconv.readthedocs.io/en/main/how_to/handle_heterogeneous_offsets.html"
                )
            add_recording_to_nwbfile(
                recording=recording,
                nwbfile=nwbfile,
                metadata=metadata,
                parent_container=parent_container,
                data_representation=data_representation,
                es_key=self.es_key,
                iterator_type=iterator_type,
                iterator_options=iterator_options,
                always_write_timestamps=always_write_timestamps,
                metadata_key=metadata_key,
            )
        else:
            add_recording_metadata_to_nwbfile(
                recording=recording,
                nwbfile=nwbfile,
                metadata=metadata,
            )
