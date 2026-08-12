import re
import warnings

from pydantic import DirectoryPath

from ..baserecordingextractorinterface import BaseRecordingExtractorInterface
from ....utils import DeepDict, get_json_schema_from_method_signature


class OpenEphysBinaryRecordingInterface(BaseRecordingExtractorInterface):
    """
    Primary data interface for converting binary OpenEphys data (.dat files).

    Uses :py:func:`~spikeinterface.extractors.read_openephys` from SpikeInterface.
    """

    display_name = "OpenEphys Binary Recording"
    associated_suffixes = (".dat", ".oebin", ".npy")
    info = "Interface for converting binary OpenEphys recording data."

    @classmethod
    def get_extractor_class(cls):
        from spikeinterface.extractors.extractor_classes import (
            OpenEphysBinaryRecordingExtractor,
        )

        return OpenEphysBinaryRecordingExtractor

    def _initialize_extractor(self, interface_kwargs: dict):
        """Override to pop stub_test parameter."""
        self.extractor_kwargs = interface_kwargs.copy()
        self.extractor_kwargs.pop("verbose", None)
        self.extractor_kwargs.pop("es_key", None)
        self.extractor_kwargs.pop("stub_test", None)

        extractor_class = self.get_extractor_class()
        extractor_instance = extractor_class(**self.extractor_kwargs)
        return extractor_instance

    @classmethod
    def get_stream_names(cls, folder_path: DirectoryPath) -> list[str]:
        """
        Get the names of available recording streams in the OpenEphys binary folder.

        Parameters
        ----------
        folder_path : DirectoryPath
            Path to directory containing OpenEphys binary files.

        Returns
        -------
        list of str
            The names of the available recording streams.
        """
        from spikeinterface.extractors.extractor_classes import (
            OpenEphysBinaryRecordingExtractor,
        )

        stream_names, _ = OpenEphysBinaryRecordingExtractor.get_streams(folder_path=folder_path)
        return stream_names

    @classmethod
    def get_source_schema(cls) -> dict:
        """
        Compile input schema for the RecordingExtractor.

        Returns
        -------
        dict
            The JSON schema for the OpenEphys binary recording interface source data,
            containing folder path and other configuration parameters. The schema
            excludes recording_id, experiment_id, and stub_test parameters.
        """
        source_schema = get_json_schema_from_method_signature(
            method=cls.__init__, exclude=["recording_id", "experiment_id", "stub_test"]
        )
        source_schema["properties"]["folder_path"][
            "description"
        ] = "Path to directory containing OpenEphys binary files."
        return source_schema

    def __init__(
        self,
        folder_path: DirectoryPath,
        *args,  # TODO: change to * (keyword only) on or after August 2026
        stream_name: str | None = None,
        block_index: int | None = None,
        stub_test: bool = False,
        verbose: bool = False,
        es_key: str = "ElectricalSeries",
        metadata_key: str | None = None,
    ):
        """
        Initialize reading of OpenEphys binary recording.

        Parameters
        ----------
        folder_path: DirectoryPath
            Path to directory containing OpenEphys binary files.
        stream_name : str, optional
            The name of the recording stream to load; only required if there is more than one stream detected.
            Call `OpenEphysRecordingInterface.get_stream_names(folder_path=...)` to see what streams are available.
        block_index : int, optional, default: None
            The index of the block to extract from the data.
        stub_test : bool, default: False
        verbose : bool, default: False
        es_key : str, default: "ElectricalSeries"
        metadata_key : str, optional
            Key that indexes this interface's entries in the dict-based metadata. Defaults to
            ``"open_ephys_recording"``.
        """
        # Handle deprecated positional arguments
        if args:
            parameter_names = [
                "stream_name",
                "block_index",
                "stub_test",
                "verbose",
                "es_key",
            ]
            num_positional_args_before_args = 1  # folder_path
            if len(args) > len(parameter_names):
                raise TypeError(
                    f"__init__() takes at most {len(parameter_names) + num_positional_args_before_args + 1} positional arguments but "
                    f"{len(args) + num_positional_args_before_args + 1} were given. "
                    "Note: Positional arguments are deprecated and will be removed on or after August 2026. "
                    "Please use keyword arguments."
                )
            positional_values = dict(zip(parameter_names, args))
            passed_as_positional = list(positional_values.keys())
            warnings.warn(
                f"Passing arguments positionally to OpenEphysBinaryRecordingInterface.__init__() is deprecated "
                f"and will be removed on or after August 2026. "
                f"The following arguments were passed positionally: {passed_as_positional}. "
                "Please use keyword arguments instead.",
                FutureWarning,
                stacklevel=2,
            )
            stream_name = positional_values.get("stream_name", stream_name)
            block_index = positional_values.get("block_index", block_index)
            stub_test = positional_values.get("stub_test", stub_test)
            verbose = positional_values.get("verbose", verbose)
            es_key = positional_values.get("es_key", es_key)

        from ._openephys_utils import _read_settings_xml

        self._xml_root = _read_settings_xml(folder_path)

        available_streams = self.get_stream_names(folder_path=folder_path)
        if len(available_streams) > 1 and stream_name is None:
            raise ValueError(
                "More than one stream is detected! "
                "Please specify which stream you wish to load with the `stream_name` argument. "
                "To see what streams are available, call "
                " `OpenEphysRecordingInterface.get_stream_names(folder_path=...)`."
            )
        if stream_name is not None and stream_name not in available_streams:
            raise ValueError(
                f"The selected stream '{stream_name}' is not in the available streams '{available_streams}'!"
            )

        super().__init__(
            folder_path=folder_path,
            stream_name=stream_name,
            block_index=block_index,
            verbose=verbose,
            es_key=es_key,
            metadata_key=metadata_key,
        )

        # ``metadata_key`` is a snake_case dict handle, not the series name. A session is a single Open Ephys
        # recording, so the default is a constant; conversions that combine several streams pass their own.
        if metadata_key is None:
            self.metadata_key = "open_ephys_recording"

        # Check if the recording has ADC channels
        recording = self.recording_extractor
        channel_ids = recording.get_channel_ids()
        neural_channels = [id for id in channel_ids if "ADC" not in id]
        if len(neural_channels) < len(channel_ids):
            self.recording_extractor = recording.select_channels(channel_ids=neural_channels)

        # Set composite channel_name for multi-stream electrode deduplication
        # When AP and LFP streams exist for the same probe, they record from the
        # same physical electrodes. Setting composite names (e.g. "AP0,LFP0") on
        # both streams lets the electrode table builder match them to the same rows,
        # avoiding duplicate entries. This follows the same approach as SpikeGLX.
        if stream_name is not None:
            band_suffixes = {"-AP": "-LFP", "-LFP": "-AP"}
            current_suffix = None
            for suffix in band_suffixes:
                if stream_name.endswith(suffix):
                    current_suffix = suffix
                    break

            if current_suffix is not None:
                companion_suffix = band_suffixes[current_suffix]
                prefix = stream_name[: -len(current_suffix)]
                companion_stream = prefix + companion_suffix
                has_companion = companion_stream in available_streams

                if has_companion:
                    channel_ids = self.recording_extractor.get_channel_ids()
                    channel_names = []
                    for channel_id in channel_ids:
                        # Extract the numeric part from channel_id (e.g. "AP1" -> "1", "LFP3" -> "3")
                        match = re.search(r"\d+$", str(channel_id))
                        channel_number = match.group() if match else str(channel_id)
                        # Composite name with both bands, alphabetically sorted
                        channel_name = f"AP{channel_number},LFP{channel_number}"
                        channel_names.append(channel_name)

                    self.recording_extractor.set_property(key="channel_name", ids=channel_ids, values=channel_names)

    def get_metadata(self, *, use_new_metadata_format: bool = False) -> DeepDict:
        from ._openephys_utils import _get_session_start_time
        from ....tools.spikeinterface.spikeinterface import _get_group_name

        metadata = super().get_metadata(use_new_metadata_format=use_new_metadata_format)

        if use_new_metadata_format:
            # State the series name here, where the metadata is produced: it is the interface's own, and it is
            # independent of ``metadata_key`` (the dict key), so re-keying an entry never renames the series.
            metadata["Ecephys"]["ElectricalSeries"][self.metadata_key]["name"] = "ElectricalSeries"

            # A probe is attached only for Neuropixels streams whose ``settings.xml`` names a part
            # number; every other stream keeps the pipeline's placeholder device, as before.
            if self.recording_extractor.has_probe():
                # The probe identity is split across the two registries: the model carries what names
                # the catalogue entry (``manufacturer`` and ``model_number``), the device carries what
                # names the individual unit (``serial_number``). Written this way,
                # ``probeinterface.get_probe(manufacturer, model_number)`` rebuilds the geometry from
                # the file.
                probe = self.recording_extractor.get_probe()
                serial_number = probe.serial_number if probe.serial_number not in (None, "", "0") else None

                # The key names the physical probe rather than the stream, because the AP and LFP
                # streams of one probe are two interfaces whose metadata has to deep-merge into one
                # entry. The serial number is the only field that identifies a unit across both.
                # Without one, the key is scoped to the interface, which is already unique per
                # ``metadata_key``, so two serial-less interfaces in a converter cannot collide on it.
                probe_index = 0  # one probe per Open Ephys stream
                device_metadata_key = (
                    f"neuropixels_{serial_number}" if serial_number else f"{self.metadata_key}_probe_{probe_index}"
                )

                # ``probe.name`` is the label the Neuropix-PXI plugin gives the probe in the signal
                # chain, so every Record Node recording it agrees on the name.
                probe_name = probe.name or f"Probe{probe_index}"
                device = dict(name=f"Neuropixels{probe_name}")
                if serial_number:
                    device["serial_number"] = serial_number

                # No model number means no model. A manufacturer on its own would have to go on
                # ``Device.manufacturer``, which pynwb 4.0 deprecates, or into a model named after its
                # maker, which states nothing.
                model_number = probe.model_name
                if model_number:
                    device_model_metadata_key = f"{probe.manufacturer}_{model_number}"
                    device["device_model_metadata_key"] = device_model_metadata_key
                    # ``model_number`` holds probeinterface's ``model_name`` verbatim, since that string
                    # is the ``get_probe`` lookup key.
                    device_model = dict(name=model_number, model_number=model_number)
                    if probe.manufacturer:
                        device_model["manufacturer"] = probe.manufacturer
                    if probe.annotations.get("description"):
                        device_model["description"] = probe.annotations["description"]
                    metadata["DeviceModels"] = {device_model_metadata_key: device_model}

                metadata["Devices"] = {device_metadata_key: device}

                # A device is only written when an electrode group references it, so the groups carry
                # the link. Only the fields the source supports are stated; the required
                # ``description`` and ``location`` are defaulted by the write pipeline.
                channel_group_names = set(_get_group_name(recording=self.recording_extractor).tolist())
                metadata["Ecephys"]["ElectrodeGroups"] = {
                    group_name: dict(name=group_name, device_metadata_key=device_metadata_key)
                    for group_name in channel_group_names
                }

        session_start_time = _get_session_start_time(element=self._xml_root)
        if session_start_time is not None:
            metadata["NWBFile"].update(session_start_time=session_start_time)
        return metadata
