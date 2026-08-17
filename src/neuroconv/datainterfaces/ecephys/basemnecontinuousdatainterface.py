"""Base interfaces for continuous data read through MNE-Python."""

from pynwb import NWBFile, TimeSeries
from pynwb.ecephys import ElectricalSeries

from ...basedatainterface import BaseDataInterface
from ...tools.mne import MNERawDataChunkIterator
from ...tools.nwb_helpers._metadata_and_file_helpers import _add_device_to_nwbfile
from ...utils import (
    DeepDict,
    get_base_schema,
)


class BaseMNEContinuousDataInterface(BaseDataInterface):
    """Parent class for interfaces that read continuous data through MNE-Python.

    A subclass builds an ``mne.io.BaseRaw`` object in :meth:`_read_raw`, and one interface writes one
    MNE channel type to one neurodata object. An MNE ``Raw`` holds channels of several kinds on a
    single shared timebase (eeg, eog, stim, mag, misc, ...), and the kinds do not all belong in the
    same NWB object, so the destination is chosen by the class that is instantiated rather than by a
    routing table inside a shared writer. Compose several interfaces to write a whole ``Raw``.

    This class holds only what every destination shares: the ``Raw``, the channels of its
    ``channel_type``, the unit those channels carry, the sampling rate, and the streaming read.
    :meth:`add_to_nwbfile` belongs to the destination subclasses.

    Scope (v1): no electrode geometry (coordinates) and no temporal alignment yet. The parent is
    ``BaseDataInterface`` (not the temporal-alignment mixin); timing is written as a regular
    ``rate`` from ``raw.info['sfreq']`` with ``starting_time=0.0``.
    """

    keywords = ("electroencephalography", "voltage", "MNE")

    # Functional Imaging File Format codes (FIFF codes) for units, as MNE stores them on
    # ``raw.info["chs"][index]["unit"]``, mapped to the unit string NWB wants. Mirrors MNE's own
    # private ``_unit2human`` so that reading a unit needs no MNE import here. MNE labels every
    # electrode voltage and every trigger line 107, so the code identifies the physical unit and
    # never the channel's role; the role is the channel type, which is why that is what an
    # interface is scoped by.
    _fiff_unit_to_name = {
        107: "volts",
        112: "teslas",
        201: "teslas/meter",
        110: "siemens",
        114: "degrees Celsius",
        6: "moles",
        210: "pixels",
    }
    # MNE's FIFF_UNIT_NONE. The channel carries no unit, which NWB still requires as a non-empty string.
    _unitless_name = "n.a."

    def __init__(
        self,
        verbose: bool = False,
        *,
        channel_type: str,
        metadata_key: str | None = None,
        **source_data,
    ):
        """
        Parameters
        ----------
        verbose : bool, default: False
            If True, print additional information.
        channel_type : str
            The MNE channel type this interface writes (``"eeg"``, ``"eog"``, ``"stim"``, ...). Only
            channels of this type are written; compose several interfaces to cover a whole ``Raw``.
        metadata_key : str, optional
            Key addressing this interface's entry in the metadata. Defaults to ``f"mne_{channel_type}"``.
        source_data : dict
            The key-value pairs of subclass-specific arguments used to build the ``Raw`` object.
        """
        super().__init__(verbose=verbose, **source_data)
        self.channel_type = channel_type
        self.metadata_key = metadata_key if metadata_key is not None else f"mne_{channel_type}"
        self.raw = self._read_raw()

        available_channel_types = self.get_channel_types()
        if channel_type not in available_channel_types:
            raise ValueError(
                f"channel_type '{channel_type}' was not found in the Raw "
                f"(available types: {', '.join(sorted(available_channel_types))})."
            )

        self._validate_homogeneous_sampling_rate()

    def _read_raw(self) -> "mne.io.BaseRaw":  # noqa: F821
        """
        Return the ``mne.io.BaseRaw`` for this interface. Implemented by subclasses.

        The returned ``Raw`` must hold channels that shared one sampling rate *in the source*. MNE's
        data model has a single ``sfreq`` per ``Raw``, so a reader handed a source with per-channel
        rates resamples the slower channels up to the fastest one, and what comes back is partly
        interpolated. Sampling rate is therefore a scoping axis alongside ``channel_type``: a format
        that stores channels at several rates is covered by several interfaces, one per rate, the way
        a multi-stream acquisition system is. The readers for such formats (``read_raw_edf``,
        ``read_raw_bdf``, ``read_raw_gdf``) take an ``exclude`` argument for exactly this purpose.
        """
        raise NotImplementedError("Subclasses must implement `_read_raw` to return an mne.io.BaseRaw object.")

    def _validate_homogeneous_sampling_rate(self) -> None:
        """
        Refuse a ``Raw`` whose channels did not share one sampling rate in the source.

        MNE reports one ``sfreq`` for the whole ``Raw`` and gives every channel the same number of
        samples, so a resampled channel is indistinguishable from a natively fast one through the
        public API. The source's own per-channel rates do survive on the reader's private extras, as
        the samples-per-record vector, which is what this reads. Readers that expose no such vector
        are the single-rate formats, where there is nothing to check.
        """
        for raw_extra in getattr(self.raw, "_raw_extras", None) or []:
            if not isinstance(raw_extra, dict) or "n_samps" not in raw_extra:
                continue

            samples_per_record = [int(value) for value in raw_extra["n_samps"]]
            # ``sel`` indexes the data channels, dropping trailing bookkeeping channels such as the
            # EDF+ annotation signal, whose sample count is unrelated to any channel's rate.
            selection = raw_extra.get("sel")
            if selection is not None:
                samples_per_record = [samples_per_record[int(index)] for index in selection]

            distinct = sorted(set(samples_per_record))
            if len(distinct) == 1:
                continue

            # ``sfreq`` is the rate of the channels with the most samples per record, so the rest
            # scale off it without needing the record length.
            sampling_frequency = float(self.raw.info["sfreq"])
            native_rates = ", ".join(f"{sampling_frequency * value / distinct[-1]:g} Hz" for value in distinct)
            raise ValueError(
                f"This source stores channels at different sampling rates ({native_rates}), which MNE "
                f"resolves by resampling the slower ones up to {sampling_frequency:g} Hz. Those "
                "interpolated samples were never recorded, so they are not written. Read one rate at a "
                "time instead, passing `exclude` to the MNE reader so the channels that remain share a "
                "rate, and compose one interface per rate."
            )

    def get_channel_types(self) -> set[str]:
        """
        Return the MNE channel types the ``Raw`` holds.

        Reading the ``Raw`` with ``preload=False`` touches only the header, so this is the cheap way to
        find out which interfaces a file needs before writing any of them.
        """
        return set(self.raw.get_channel_types())

    @property
    def channel_indices(self) -> list[int]:
        """Indices into the ``Raw`` of the channels this interface writes, in the source's own order."""
        return [
            channel_index
            for channel_index, channel_type in enumerate(self.raw.get_channel_types())
            if channel_type == self.channel_type
        ]

    @property
    def channel_names(self) -> list[str]:
        """Names of the channels this interface writes."""
        return [self.raw.ch_names[channel_index] for channel_index in self.channel_indices]

    @property
    def unit(self) -> str:
        """The NWB unit string for these channels, read from the FIFF unit code MNE stores on them."""
        unit_code = int(self.raw.info["chs"][self.channel_indices[0]]["unit"])
        return self._fiff_unit_to_name.get(unit_code, self._unitless_name)

    def _get_data(self, stub_test: bool):
        """
        Return this interface's channels, shaped (n_times, n_channels).

        A stub is small by construction, so it is read directly through the ``Raw``'s own start/stop; the
        full write goes through the iterator so a ``Raw`` opened with ``preload=False`` is never
        materialized in memory. MNE returns (n_channels, n_times), which both paths transpose.
        """
        if stub_test:
            return self.raw.get_data(picks=self.channel_indices, start=0, stop=min(100, self.raw.n_times)).T

        return MNERawDataChunkIterator(raw=self.raw, picks=self.channel_indices)


class BaseMNEElectricalSeriesInterface(BaseMNEContinuousDataInterface):
    """Writes one MNE channel type as an ``ElectricalSeries`` plus a minimal electrodes table.

    For the channel types that are voltages measured through electrodes placed on or in neural tissue,
    which is what the electrodes table describes. ``eog``, ``ecg`` and ``emg`` are electrode voltages
    too, but of eye, heart and muscle, so they belong to :class:`BaseMNETimeSeriesInterface`.

    This destination is interim: biopotential signals want their own extension, and when one exists the
    question of what belongs in an ``ElectricalSeries`` is answered there rather than here.
    """

    # The key the ecephys write pipeline already uses for its placeholder device and electrode group.
    # Sharing it is what keeps a converter that mixes this interface with a SpikeInterface-backed one
    # valid: the registry rejects one device name registered under two different keys.
    _placeholder_metadata_key = "default_metadata_key"

    def __init__(
        self,
        verbose: bool = False,
        *,
        channel_type: str = "eeg",
        metadata_key: str | None = None,
        **source_data,
    ):
        super().__init__(verbose=verbose, channel_type=channel_type, metadata_key=metadata_key, **source_data)

    def get_metadata_schema(self) -> dict:
        """
        Compile the metadata schema.

        The registries are objects keyed by ``metadata_key``, and the entries stay permissive: an entry is
        passed to a pynwb constructor, so it may legitimately carry any field that constructor takes. Only
        the shape is pinned. This interface speaks the dict-based format alone, so there is no companion
        schema for the old list-based one.
        """
        metadata_schema = super().get_metadata_schema()
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
        )
        return metadata_schema

    def get_metadata(self) -> DeepDict:
        """Return the ElectricalSeries entry, plus the device and electrode group backing it."""
        metadata = super().get_metadata()

        # An MNE `Raw` carries no acquisition-device identity, so the device is the same placeholder the
        # ecephys write pipeline uses when a recording names none. A subclass that can read the real
        # hardware from its source overrides this entry.
        metadata["Devices"] = {
            self._placeholder_metadata_key: dict(name="PlaceholderElectrodeDevice"),
        }
        metadata["Ecephys"] = dict(
            ElectrodeGroups={
                self._placeholder_metadata_key: dict(
                    name="ElectrodeGroup",
                    description=f"The '{self.channel_type}' channels of the MNE Raw object.",
                    location="unknown",
                    device_metadata_key=self._placeholder_metadata_key,
                )
            },
            ElectricalSeries={
                self.metadata_key: dict(
                    name="ElectricalSeries",
                    description=f"MNE channel type '{self.channel_type}', imported through MNE-Python.",
                )
            },
        )
        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *,
        stub_test: bool = False,
        write_electrical_series: bool = True,
    ) -> None:
        """
        Add this interface's channels to an NWBFile as an ElectricalSeries plus an electrodes table.

        Parameters
        ----------
        nwbfile : NWBFile
            The in-memory NWBFile to add the data to.
        metadata : dict, optional
            Metadata dictionary. If None, ``get_metadata`` is used.
        stub_test : bool, default: False
            If True, only a small slice of samples is written (for fast tests).
        write_electrical_series : bool, default: True
            If False, only the device, electrode group, and electrodes are written (no ElectricalSeries).
        """
        if metadata is None:
            metadata = self.get_metadata()

        ecephys_metadata = metadata["Ecephys"]

        for group_metadata in ecephys_metadata["ElectrodeGroups"].values():
            if group_metadata["name"] in nwbfile.electrode_groups:
                continue
            group_kwargs = dict(group_metadata)
            device = _add_device_to_nwbfile(
                nwbfile=nwbfile, metadata=metadata, metadata_key=group_kwargs.pop("device_metadata_key")
            )
            nwbfile.create_electrode_group(**group_kwargs, device=device)

        # v1 puts this interface's channels in one group: the Raw carries no grouping to split on.
        group_metadata = next(iter(ecephys_metadata["ElectrodeGroups"].values()))
        electrode_group = nwbfile.electrode_groups[group_metadata["name"]]
        electrode_location = group_metadata["location"]

        existing_columns = nwbfile.electrodes.colnames if nwbfile.electrodes is not None else ()
        if "channel_name" not in existing_columns:
            nwbfile.add_electrode_column(
                name="channel_name",
                description="The name of the channel as reported by the source recording.",
            )

        channel_names = self.channel_names
        number_of_existing_electrodes = len(nwbfile.electrodes) if nwbfile.electrodes is not None else 0
        for channel_name in channel_names:
            # v1 writes no coordinates: only the required `group`/`location` plus `channel_name`.
            nwbfile.add_electrode(
                group=electrode_group,
                location=electrode_location,
                channel_name=channel_name,
            )
        electrode_table_indices = list(
            range(number_of_existing_electrodes, number_of_existing_electrodes + len(channel_names))
        )

        if not write_electrical_series:
            return

        electrode_table_region = nwbfile.create_electrode_table_region(
            region=electrode_table_indices,
            description="The electrodes for this ElectricalSeries.",
        )

        electrical_series_metadata = ecephys_metadata["ElectricalSeries"][self.metadata_key]
        electrical_series = ElectricalSeries(
            name=electrical_series_metadata["name"],
            description=electrical_series_metadata["description"],
            data=self._get_data(stub_test=stub_test),
            electrodes=electrode_table_region,
            rate=float(self.raw.info["sfreq"]),
            starting_time=0.0,
            conversion=1.0,  # MNE data is already in volts, the fixed unit of ElectricalSeries.
        )
        nwbfile.add_acquisition(electrical_series)


class BaseMNETimeSeriesInterface(BaseMNEContinuousDataInterface):
    """Writes one MNE channel type as a ``TimeSeries``, carrying the unit MNE assigned that type.

    For every channel kind that is not a neural electrode voltage: the auxiliary electrode recordings
    (``eog``, ``ecg``, ``emg``), the trigger lines (``stim``), which are not measurements of tissue at
    all, the magnetometers and gradiometers (``mag``, ``grad``) in teslas and teslas per meter, and the
    arbitrary-unit channels (``misc``, ``bio``, ``resp``, ``gsr``, ``temperature``).
    """

    def get_metadata(self) -> DeepDict:
        """Return the TimeSeries entry for this interface's channel type."""
        metadata = super().get_metadata()

        channel_names = ", ".join(self.channel_names)
        metadata["TimeSeries"][self.metadata_key] = dict(
            name=f"TimeSeries{self.channel_type.upper()}",
            description=f"MNE channel type '{self.channel_type}', imported through MNE-Python. "
            f"Channels: {channel_names}",
            unit=self.unit,
        )
        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *,
        stub_test: bool = False,
    ) -> None:
        """
        Add this interface's channels to an NWBFile as a TimeSeries.

        Parameters
        ----------
        nwbfile : NWBFile
            The in-memory NWBFile to add the data to.
        metadata : dict, optional
            Metadata dictionary. If None, ``get_metadata`` is used.
        stub_test : bool, default: False
            If True, only a small slice of samples is written (for fast tests).
        """
        if metadata is None:
            metadata = self.get_metadata()

        time_series_metadata = metadata["TimeSeries"][self.metadata_key]
        time_series = TimeSeries(
            name=time_series_metadata["name"],
            description=time_series_metadata["description"],
            unit=time_series_metadata["unit"],
            data=self._get_data(stub_test=stub_test),
            rate=float(self.raw.info["sfreq"]),
            starting_time=0.0,
            conversion=1.0,  # MNE applies the calibration on read, so the values are already in `unit`.
        )
        nwbfile.add_acquisition(time_series)
