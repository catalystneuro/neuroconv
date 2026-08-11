"""Base interface for continuous data read through MNE-Python."""

from pynwb import NWBFile
from pynwb.device import Device
from pynwb.ecephys import ElectricalSeries, ElectrodeGroup

from ...basedatainterface import BaseDataInterface
from ...utils import (
    DeepDict,
    get_base_schema,
    get_schema_from_hdmf_class,
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
            If True, print additional information.
        es_key : str, default: "ElectricalSeries"
            The key of this ElectricalSeries in the metadata dictionary.
        metadata_key : str, optional
            Key of this interface's ElectricalSeries in the metadata. Defaults to ``es_key``.
        source_data : dict
            The key-value pairs of subclass-specific arguments used to build the ``Raw`` object.
        """
        super().__init__(verbose=verbose, **source_data)
        self.es_key = es_key
        self.metadata_key = metadata_key if metadata_key is not None else es_key
        self.raw = self._read_raw()

    def _read_raw(self) -> "mne.io.BaseRaw":  # noqa: F821
        """Return the ``mne.io.BaseRaw`` for this interface. Implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement `_read_raw` to return an mne.io.BaseRaw object.")

    def get_metadata_schema(self) -> dict:
        """Compile the metadata schema, adding the Ecephys Device/ElectrodeGroup/ElectricalSeries block."""
        metadata_schema = super().get_metadata_schema()
        metadata_schema["properties"]["Ecephys"] = get_base_schema(tag="Ecephys")
        metadata_schema["properties"]["Ecephys"]["required"] = ["Device", "ElectrodeGroup"]
        metadata_schema["properties"]["Ecephys"]["properties"] = dict(
            Device=dict(type="array", minItems=1, items={"$ref": "#/properties/Ecephys/definitions/Device"}),
            ElectrodeGroup=dict(
                type="array", minItems=1, items={"$ref": "#/properties/Ecephys/definitions/ElectrodeGroup"}
            ),
        )
        metadata_schema["properties"]["Ecephys"]["definitions"] = dict(
            Device=get_schema_from_hdmf_class(Device),
            ElectrodeGroup=get_schema_from_hdmf_class(ElectrodeGroup),
        )
        metadata_schema["properties"]["Ecephys"]["properties"].update(
            {self.es_key: get_schema_from_hdmf_class(ElectricalSeries)}
        )
        return metadata_schema

    def get_metadata(self) -> DeepDict:
        """Return default metadata: one device, one electrode group, and the ElectricalSeries entry."""
        metadata = super().get_metadata()
        metadata["Ecephys"] = dict(
            Device=[dict(name="DeviceEEG", description="Recording device, imported through MNE-Python.")],
            ElectrodeGroup=[
                dict(
                    name="ElectrodeGroup",
                    description="All channels from the MNE Raw object.",
                    location="unknown",
                    device="DeviceEEG",
                )
            ],
        )
        metadata["Ecephys"][self.es_key] = dict(
            name=self.es_key,
            description=f"Continuous voltage data imported through MNE-Python for {self.es_key}.",
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

        for device_metadata in ecephys_metadata["Device"]:
            if device_metadata["name"] not in nwbfile.devices:
                nwbfile.create_device(**device_metadata)

        for group_metadata in ecephys_metadata["ElectrodeGroup"]:
            if group_metadata["name"] in nwbfile.electrode_groups:
                continue
            group_kwargs = dict(group_metadata)
            device_name = group_kwargs.pop("device")
            nwbfile.create_electrode_group(**group_kwargs, device=nwbfile.devices[device_name])

        group_metadata = ecephys_metadata["ElectrodeGroup"][0]
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
        data = self.raw.get_data()
        if stub_test:
            data = data[:, : min(100, data.shape[1])]

        electrical_series_metadata = ecephys_metadata[self.es_key]
        electrical_series = ElectricalSeries(
            name=electrical_series_metadata["name"],
            description=electrical_series_metadata["description"],
            data=data.T,
            electrodes=electrode_table_region,
            rate=float(self.raw.info["sfreq"]),
            starting_time=0.0,
            conversion=1.0,  # MNE data is already in volts, the fixed unit of ElectricalSeries.
        )
        nwbfile.add_acquisition(electrical_series)
