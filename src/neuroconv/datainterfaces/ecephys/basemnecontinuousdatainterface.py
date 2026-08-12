"""Base interface for continuous data read through MNE-Python."""

from pynwb import NWBFile
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

    A subclass builds an ``mne.io.BaseRaw`` object in :meth:`_read_raw`; this base maps it to an
    ``ElectricalSeries`` plus a minimal electrodes table (channel name, group, location).

    Scope (v1): voltage channels meant for an ``ElectricalSeries`` only. No electrode geometry
    (coordinates), no channel-type partitioning, and no temporal alignment yet. The parent is
    ``BaseDataInterface`` (not the temporal-alignment mixin); timing is written as a regular
    ``rate`` from ``raw.info['sfreq']`` with ``starting_time=0.0``.
    """

    keywords = ("electroencephalography", "voltage", "MNE")

    # The key the ecephys write pipeline already uses for its placeholder device and electrode group.
    # Sharing it is what keeps a converter that mixes this interface with a SpikeInterface-backed one
    # valid: the registry rejects one device name registered under two different keys.
    _placeholder_metadata_key = "default_metadata_key"

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
        """Return default metadata: the placeholder device, one electrode group, and the ElectricalSeries entry."""
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
                    description="All channels from the MNE Raw object.",
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
        Add the MNE ``Raw`` data to an NWBFile as an ElectricalSeries plus a minimal electrodes table.

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

        # v1 puts every channel in one group: the Raw carries no grouping to split on.
        group_metadata = next(iter(ecephys_metadata["ElectrodeGroups"].values()))
        electrode_group = nwbfile.electrode_groups[group_metadata["name"]]
        electrode_location = group_metadata["location"]

        existing_columns = nwbfile.electrodes.colnames if nwbfile.electrodes is not None else ()
        if "channel_name" not in existing_columns:
            nwbfile.add_electrode_column(
                name="channel_name",
                description="The name of the channel as reported by the source recording.",
            )

        channel_names = self.raw.ch_names
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

        # MNE returns data as (n_channels, n_times) in SI volts; ElectricalSeries expects (n_times, n_channels).
        # A stub is small by construction, so it is read directly; the full write goes through the iterator
        # so that a Raw opened with `preload=False` is never materialized in memory.
        if stub_test:
            data = self.raw.get_data(start=0, stop=min(100, self.raw.n_times)).T
        else:
            data = MNERawDataChunkIterator(raw=self.raw)

        electrical_series_metadata = ecephys_metadata["ElectricalSeries"][self.metadata_key]
        electrical_series = ElectricalSeries(
            name=electrical_series_metadata["name"],
            description=electrical_series_metadata["description"],
            data=data,
            electrodes=electrode_table_region,
            rate=float(self.raw.info["sfreq"]),
            starting_time=0.0,
            conversion=1.0,  # MNE data is already in volts, the fixed unit of ElectricalSeries.
        )
        nwbfile.add_acquisition(electrical_series)
