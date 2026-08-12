"""Base interface for continuous data read through MNE-Python."""

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

    A subclass builds an ``mne.io.BaseRaw`` object in :meth:`_read_raw`; this base partitions its
    channels by MNE channel type. The electrode kinds become one ``ElectricalSeries`` backed by a
    minimal electrodes table (channel name, group, location), and every other kind the ``Raw`` holds
    becomes a ``TimeSeries`` of its own, one per channel type, carrying that type's unit.

    Scope (v1): no electrode geometry (coordinates) and no temporal alignment yet. The parent is
    ``BaseDataInterface`` (not the temporal-alignment mixin); timing is written as a regular
    ``rate`` from ``raw.info['sfreq']`` with ``starting_time=0.0``.
    """

    keywords = ("electroencephalography", "voltage", "MNE")

    # The key the ecephys write pipeline already uses for its placeholder device and electrode group.
    # Sharing it is what keeps a converter that mixes this interface with a SpikeInterface-backed one
    # valid: the registry rejects one device name registered under two different keys.
    _placeholder_metadata_key = "default_metadata_key"

    # The MNE channel types written as an ElectricalSeries: voltages measured through electrodes placed
    # on or in neural tissue, which is what the electrodes table describes. Every other kind MNE can
    # hold goes to a TimeSeries, including the other voltages (eog, ecg, emg are electrode recordings
    # too, but of eye, heart and muscle) and the trigger lines, which are not measurements of tissue at
    # all. This split is interim: biopotential signals want their own extension, and when one exists the
    # question of what belongs in an ElectricalSeries is answered there rather than here.
    _electrical_series_channel_types = ("eeg", "seeg", "ecog", "dbs")

    # FIFF unit codes, as MNE stores them on ``raw.info["chs"][index]["unit"]``, to the unit string NWB
    # wants. Mirrors MNE's own private ``_unit2human`` so that reading a unit needs no MNE import here.
    # MNE labels every electrode voltage and every trigger line 107, so the code identifies the physical
    # unit and never the channel's role; the role comes from the channel type.
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
        metadata_key: str = "ElectricalSeries",
        **source_data,
    ):
        """
        Parameters
        ----------
        verbose : bool, default: False
            If True, print additional information.
        metadata_key : str, default: "ElectricalSeries"
            Key of this interface's ElectricalSeries in ``metadata["Ecephys"]["ElectricalSeries"]``.
        source_data : dict
            The key-value pairs of subclass-specific arguments used to build the ``Raw`` object.
        """
        super().__init__(verbose=verbose, **source_data)
        self.metadata_key = metadata_key
        self.raw = self._read_raw()

    def _read_raw(self) -> "mne.io.BaseRaw":  # noqa: F821
        """Return the ``mne.io.BaseRaw`` for this interface. Implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement `_read_raw` to return an mne.io.BaseRaw object.")

    def _partition_channels(self) -> tuple[list[int], dict[str, list[int]]]:
        """
        Split the ``Raw``'s channels into the ElectricalSeries ones and the TimeSeries ones.

        Returns
        -------
        electrical_series_channel_indices : list of int
            Indices of the channels written as the ElectricalSeries, empty when the ``Raw`` holds none.
        time_series_channel_indices : dict
            Indices of every other channel, keyed by MNE channel type, one TimeSeries per key. Ordered by
            first appearance in the ``Raw`` so the written objects follow the source's own channel order.
        """
        electrical_series_channel_indices = []
        time_series_channel_indices = {}
        for channel_index, channel_type in enumerate(self.raw.get_channel_types()):
            if channel_type in self._electrical_series_channel_types:
                electrical_series_channel_indices.append(channel_index)
            else:
                time_series_channel_indices.setdefault(channel_type, []).append(channel_index)

        return electrical_series_channel_indices, time_series_channel_indices

    def _get_unit(self, channel_index: int) -> str:
        """Return the NWB unit string for a channel, read from the FIFF unit code MNE stores on it."""
        unit_code = int(self.raw.info["chs"][channel_index]["unit"])
        return self._fiff_unit_to_name.get(unit_code, self._unitless_name)

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
        """Return default metadata: an entry per written object, plus the device and group backing them."""
        metadata = super().get_metadata()

        electrical_series_channel_indices, time_series_channel_indices = self._partition_channels()

        if electrical_series_channel_indices:
            # An MNE `Raw` carries no acquisition-device identity, so the device is the same placeholder
            # the ecephys write pipeline uses when a recording names none. A subclass that can read the
            # real hardware from its source overrides this entry.
            metadata["Devices"] = {
                self._placeholder_metadata_key: dict(name="PlaceholderElectrodeDevice"),
            }
            metadata["Ecephys"] = dict(
                ElectrodeGroups={
                    self._placeholder_metadata_key: dict(
                        name="ElectrodeGroup",
                        description="All electrode channels from the MNE Raw object.",
                        location="unknown",
                        device_metadata_key=self._placeholder_metadata_key,
                    )
                },
                ElectricalSeries={
                    self.metadata_key: dict(
                        name="ElectricalSeries",
                        description="Continuous voltage data imported through MNE-Python.",
                    )
                },
            )

        for channel_type, channel_indices in time_series_channel_indices.items():
            channel_names = ", ".join(self.raw.ch_names[index] for index in channel_indices)
            metadata["TimeSeries"][channel_type] = dict(
                name=f"TimeSeries{channel_type.upper()}",
                description=f"MNE channel type '{channel_type}', imported through MNE-Python. "
                f"Channels: {channel_names}",
                unit=self._get_unit(channel_indices[0]),
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
        Add the MNE ``Raw`` data to an NWBFile, partitioned by channel type.

        Electrode channels (eeg, seeg, ecog, dbs) become one ElectricalSeries backed by an electrodes
        table; every other channel kind the ``Raw`` holds becomes a TimeSeries, one per channel type,
        carrying that type's own unit. Nothing the ``Raw`` holds is dropped.

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
            The TimeSeries written for the other channel types are unaffected.
        """
        if metadata is None:
            metadata = self.get_metadata()

        electrical_series_channel_indices, time_series_channel_indices = self._partition_channels()

        for channel_type, channel_indices in time_series_channel_indices.items():
            self._add_time_series_to_nwbfile(
                nwbfile=nwbfile,
                metadata=metadata,
                channel_type=channel_type,
                channel_indices=channel_indices,
                stub_test=stub_test,
            )

        if not electrical_series_channel_indices:
            return

        ecephys_metadata = metadata["Ecephys"]

        for group_metadata in ecephys_metadata["ElectrodeGroups"].values():
            if group_metadata["name"] in nwbfile.electrode_groups:
                continue
            group_kwargs = dict(group_metadata)
            device = _add_device_to_nwbfile(
                nwbfile=nwbfile, metadata=metadata, metadata_key=group_kwargs.pop("device_metadata_key")
            )
            nwbfile.create_electrode_group(**group_kwargs, device=device)

        # v1 puts every electrode channel in one group: the Raw carries no grouping to split on.
        group_metadata = next(iter(ecephys_metadata["ElectrodeGroups"].values()))
        electrode_group = nwbfile.electrode_groups[group_metadata["name"]]
        electrode_location = group_metadata["location"]

        existing_columns = nwbfile.electrodes.colnames if nwbfile.electrodes is not None else ()
        if "channel_name" not in existing_columns:
            nwbfile.add_electrode_column(
                name="channel_name",
                description="The name of the channel as reported by the source recording.",
            )

        number_of_existing_electrodes = len(nwbfile.electrodes) if nwbfile.electrodes is not None else 0
        for channel_index in electrical_series_channel_indices:
            # v1 writes no coordinates: only the required `group`/`location` plus `channel_name`.
            nwbfile.add_electrode(
                group=electrode_group,
                location=electrode_location,
                channel_name=self.raw.ch_names[channel_index],
            )
        electrode_table_indices = list(
            range(
                number_of_existing_electrodes,
                number_of_existing_electrodes + len(electrical_series_channel_indices),
            )
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
            data=self._get_data(channel_indices=electrical_series_channel_indices, stub_test=stub_test),
            electrodes=electrode_table_region,
            rate=float(self.raw.info["sfreq"]),
            starting_time=0.0,
            conversion=1.0,  # MNE data is already in volts, the fixed unit of ElectricalSeries.
        )
        nwbfile.add_acquisition(electrical_series)

    def _add_time_series_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict,
        channel_type: str,
        channel_indices: list[int],
        stub_test: bool,
    ) -> None:
        """Write one MNE channel type that does not belong in an ElectricalSeries as a TimeSeries."""
        time_series_metadata = metadata["TimeSeries"][channel_type]
        time_series = TimeSeries(
            name=time_series_metadata["name"],
            description=time_series_metadata["description"],
            unit=time_series_metadata["unit"],
            data=self._get_data(channel_indices=channel_indices, stub_test=stub_test),
            rate=float(self.raw.info["sfreq"]),
            starting_time=0.0,
            conversion=1.0,  # MNE applies the calibration on read, so the values are already in `unit`.
        )
        nwbfile.add_acquisition(time_series)

    def _get_data(self, channel_indices: list[int], stub_test: bool):
        """
        Return the data for a set of channels, shaped (n_times, n_channels).

        A stub is small by construction, so it is read directly through the ``Raw``'s own start/stop; the
        full write goes through the iterator so a ``Raw`` opened with ``preload=False`` is never
        materialized in memory. MNE returns (n_channels, n_times), which both paths transpose.
        """
        if stub_test:
            return self.raw.get_data(picks=channel_indices, start=0, stop=min(100, self.raw.n_times)).T

        return MNERawDataChunkIterator(raw=self.raw, picks=channel_indices)
