"""Writers that put an ``mne.io.BaseRaw``'s channels into an NWBFile without going through an interface.

The module is public; the writer is not. ``_add_mne_raw_to_nwbfile`` drops its underscore once at least
two formats ship on the MNE base, so the shape is settled against more than one caller before anyone can
depend on it. Mirrors ``tools/spikeinterface/spikeinterface.py`` and ``tools/neo/neo.py`` in layout.

The scoping matches the interfaces exactly: **one call writes one MNE channel type to one neurodata
object**, and the destination is the caller's choice rather than something derived here. An
``mne.io.BaseRaw`` holds channels of several kinds on one shared timebase and they do not all belong in
the same NWB object, but which kind belongs where is a judgement that changes (whether ``eog`` counts as
a neural electrode voltage is the call most likely to be revisited, and a biopotential extension would
move it again). Deriving it in a second place would give the codebase two answers that can disagree, so
the caller loops over ``raw.get_channel_types()`` and calls this once per type.
"""

from pynwb import NWBFile, TimeSeries
from pynwb.ecephys import ElectricalSeries

from .mnerawdatachunkiterator import MNERawDataChunkIterator
from ..nwb_helpers._metadata_and_file_helpers import _add_device_to_nwbfile

# Functional Imaging File Format codes (FIFF codes) for units, as MNE stores them on
# ``raw.info["chs"][index]["unit"]``, mapped to the unit string NWB wants. Mirrors MNE's own private
# ``_unit2human`` so that reading a unit needs no MNE import here.
_FIFF_UNIT_TO_NAME = {
    107: "volts",
    112: "teslas",
    201: "teslas/meter",
    110: "siemens",
    114: "degrees Celsius",
    6: "moles",
    210: "pixels",
}
# MNE's FIFF_UNIT_NONE. The channel carries no unit, which NWB still requires as a non-empty string.
_UNITLESS_NAME = "n.a."


def _channel_indices(raw, channel_type: str) -> list[int]:
    """Indices into the ``Raw`` of the channels of ``channel_type``, in the source's own order."""
    return [index for index, type_ in enumerate(raw.get_channel_types()) if type_ == channel_type]


def _channel_unit(raw, channel_indices: list[int]) -> str:
    """The NWB unit string for these channels, read from the FIFF unit code MNE stores on them."""
    unit_code = int(raw.info["chs"][channel_indices[0]]["unit"])
    return _FIFF_UNIT_TO_NAME.get(unit_code, _UNITLESS_NAME)


def _channel_data(raw, channel_indices: list[int], stub_test: bool):
    """
    Return these channels shaped (n_times, n_channels).

    A stub is small by construction, so it is read directly through the ``Raw``'s own start/stop; the
    full write goes through the iterator so a ``Raw`` opened with ``preload=False`` is never
    materialized in memory. MNE returns (n_channels, n_times), which both paths transpose.
    """
    if stub_test:
        return raw.get_data(picks=channel_indices, start=0, stop=min(100, raw.n_times)).T

    return MNERawDataChunkIterator(raw=raw, picks=channel_indices)


def _add_mne_raw_to_nwbfile(
    raw,
    nwbfile: NWBFile,
    metadata: dict,
    *,
    channel_type: str,
    metadata_key: str | None = None,
    write_as: str = "ElectricalSeries",
    stub_test: bool = False,
    write_electrical_series: bool = True,
) -> None:
    """
    Write one MNE channel type of a ``Raw`` into an NWBFile.

    Parameters
    ----------
    raw : mne.io.BaseRaw
        The recording to read. Opened with ``preload=False`` it is never materialized in memory.
    nwbfile : NWBFile
        The in-memory NWBFile to add the data to.
    metadata : dict
        Dict-based metadata. ``write_as="ElectricalSeries"`` reads ``metadata["Devices"]``,
        ``metadata["Ecephys"]["ElectrodeGroups"]`` and ``metadata["Ecephys"]["ElectricalSeries"]``;
        ``write_as="TimeSeries"`` reads ``metadata["TimeSeries"]``. Both are keyed by ``metadata_key``.
    channel_type : str
        The MNE channel type to write (``"eeg"``, ``"seeg"``, ``"eog"``, ``"stim"``, ...). Only channels
        of this type are written; call once per type to cover a whole ``Raw``.
    metadata_key : str, optional
        Key addressing this call's entry in the metadata. Defaults to ``f"mne_{channel_type}"``.
    write_as : {"ElectricalSeries", "TimeSeries"}, default: "ElectricalSeries"
        The destination. This is the caller's decision, not something derived from ``channel_type``, so
        that the map from channel type to destination lives in exactly one place in the codebase.
    stub_test : bool, default: False
        If True, only a small slice of samples is written (for fast tests).
    write_electrical_series : bool, default: True
        ``ElectricalSeries`` only. If False, the device, electrode group and electrodes are written but
        the series is not.

    Raises
    ------
    ValueError
        If ``channel_type`` is not present in the ``Raw``, or ``write_as`` is not a known destination.
    """
    if write_as not in ("ElectricalSeries", "TimeSeries"):
        raise ValueError(f"`write_as` must be 'ElectricalSeries' or 'TimeSeries', not {write_as!r}.")

    channel_indices = _channel_indices(raw=raw, channel_type=channel_type)
    if not channel_indices:
        available = ", ".join(sorted(set(raw.get_channel_types())))
        raise ValueError(f"channel_type '{channel_type}' was not found in the Raw (available types: {available}).")

    metadata_key = metadata_key if metadata_key is not None else f"mne_{channel_type}"
    channel_names = [raw.ch_names[index] for index in channel_indices]
    sampling_frequency = float(raw.info["sfreq"])

    if write_as == "TimeSeries":
        time_series_metadata = metadata["TimeSeries"][metadata_key]
        nwbfile.add_acquisition(
            TimeSeries(
                name=time_series_metadata["name"],
                description=time_series_metadata["description"],
                unit=time_series_metadata["unit"],
                data=_channel_data(raw=raw, channel_indices=channel_indices, stub_test=stub_test),
                rate=sampling_frequency,
                starting_time=0.0,
                conversion=1.0,  # MNE applies the calibration on read, so the values are already in `unit`.
            )
        )
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

    # v1 puts one call's channels in one group: the Raw carries no grouping to split on.
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
    for channel_name in channel_names:
        # v1 writes no coordinates: only the required `group`/`location` plus `channel_name`.
        nwbfile.add_electrode(group=electrode_group, location=electrode_location, channel_name=channel_name)
    electrode_table_indices = list(
        range(number_of_existing_electrodes, number_of_existing_electrodes + len(channel_names))
    )

    if not write_electrical_series:
        return

    electrode_table_region = nwbfile.create_electrode_table_region(
        region=electrode_table_indices,
        description="The electrodes for this ElectricalSeries.",
    )

    electrical_series_metadata = ecephys_metadata["ElectricalSeries"][metadata_key]
    nwbfile.add_acquisition(
        ElectricalSeries(
            name=electrical_series_metadata["name"],
            description=electrical_series_metadata["description"],
            data=_channel_data(raw=raw, channel_indices=channel_indices, stub_test=stub_test),
            electrodes=electrode_table_region,
            rate=sampling_frequency,
            starting_time=0.0,
            conversion=1.0,  # MNE data is already in volts, the fixed unit of ElectricalSeries.
        )
    )
