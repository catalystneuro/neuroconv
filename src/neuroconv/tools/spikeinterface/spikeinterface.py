import warnings
from collections import defaultdict
from copy import deepcopy
from typing import Any, Literal, Optional

import numpy as np
import psutil
import pynwb
from hdmf.data_utils import AbstractDataChunkIterator
from pydantic import FilePath
from spikeinterface import BaseRecording, BaseSorting, SortingAnalyzer
from spikeinterface.core.segmentutils import AppendSegmentRecording

from .spikeinterfacerecordingdatachunkiterator import (
    SpikeInterfaceRecordingDataChunkIterator,
)
from ..nwb_helpers import get_module, make_or_load_nwbfile
from ...utils import (
    DeepDict,
    calculate_regular_series_rate,
)
from ...utils.str_utils import human_readable_size


def add_recording_to_nwbfile(
    recording: BaseRecording,
    nwbfile: pynwb.NWBFile,
    metadata: dict | None = None,
    write_as: Literal["raw", "processed", "lfp"] = "raw",
    es_key: str | None = None,
    write_electrical_series: bool = True,
    write_scaled: bool = False,
    iterator_type: str = "v2",
    iterator_options: dict | None = None,
    iterator_opts: dict | None = None,
    always_write_timestamps: bool = False,
):
    """
    Adds traces from recording object as ElectricalSeries to an NWBFile object.

    Parameters
    ----------
    recording : SpikeInterfaceRecording
        A recording extractor from spikeinterface
    nwbfile : NWBFile
        nwb file to which the recording information is to be added
    metadata : dict, optional
        metadata info for constructing the nwb file.
        Should be of the format::

            metadata['Ecephys']['ElectricalSeries'] = dict(
                name=my_name,
                description=my_description
            )
    write_as : {'raw', 'processed', 'lfp'}
        How to save the traces data in the nwb file. Options:
        - 'raw': save it in acquisition
        - 'processed': save it as FilteredEphys, in a processing module
        - 'lfp': save it as LFP, in a processing module
    es_key : str, optional
        Key in metadata dictionary containing metadata info for the specific electrical series
    iterator_type: {"v2",  None}, default: 'v2'
        The type of DataChunkIterator to use.
        'v2' is the locally developed SpikeInterfaceRecordingDataChunkIterator, which offers full control over chunking.
        None: write the TimeSeries with no memory chunking.
    iterator_options: dict, optional
        Dictionary of options for the iterator.
        See https://hdmf.readthedocs.io/en/stable/hdmf.data_utils.html#hdmf.data_utils.GenericDataChunkIterator
        for the full list of options.
    iterator_opts: dict, optional
        Deprecated. Use 'iterator_options' instead.
    always_write_timestamps : bool, default: False
        Set to True to always write timestamps.
        By default (False), the function checks if the timestamps are uniformly sampled, and if so, stores the data
        using a regular sampling rate instead of explicit timestamps. If set to True, timestamps will be written
        explicitly, regardless of whether the sampling rate is uniform.

    Notes
    -----
    Missing keys in an element of metadata['Ecephys']['ElectrodeGroup'] will be auto-populated with defaults
    whenever possible.
    """

    # Handle deprecated iterator_opts parameter
    if iterator_opts is not None:
        warnings.warn(
            "The 'iterator_opts' parameter is deprecated and will be removed on or after March 2026. "
            "Use 'iterator_options' instead.",
            FutureWarning,
            stacklevel=2,
        )
        if iterator_options is not None:
            raise ValueError("Cannot specify both 'iterator_opts' and 'iterator_options'. Use 'iterator_options'.")
        iterator_options = iterator_opts

    if metadata is None:
        metadata = _get_default_ecephys_metadata()

    add_recording_metadata_to_nwbfile(recording=recording, nwbfile=nwbfile, metadata=metadata)
    # Early termination just adds the metadata
    if not write_electrical_series:
        warning_message = (
            "`write_electrical_series` is deprecated and will be removed in or after October 2025."
            "If only metadata addition is desired, use `add_recording_metadata_to_nwbfile` instead."
        )

        warnings.warn(warning_message, stacklevel=2)
        return None

    number_of_segments = recording.get_num_segments()
    for segment_index in range(number_of_segments):
        _add_recording_segment_to_nwbfile(
            recording=recording,
            nwbfile=nwbfile,
            segment_index=segment_index,
            metadata=metadata,
            write_as=write_as,
            es_key=es_key,
            write_scaled=write_scaled,
            iterator_type=iterator_type,
            iterator_opts=iterator_options,
            always_write_timestamps=always_write_timestamps,
        )


def add_sorting_to_nwbfile(
    sorting: BaseSorting,
    nwbfile: pynwb.NWBFile | None = None,
    unit_ids: list[str] | list[int] | None = None,
    property_descriptions: dict | None = None,
    skip_properties: list[str] | None = None,
    write_as: Literal["units", "processing"] = "units",
    units_name: str = "units",
    units_description: str = "Autogenerated by neuroconv.",
    waveform_means: np.ndarray | None = None,
    waveform_sds: np.ndarray | None = None,
    unit_electrode_indices: list[list[int]] | None = None,
    null_values_for_properties: dict | None = None,
):
    """Add sorting data (units and their properties) to an NWBFile.

    This function serves as a convenient wrapper around `add_units_table` to match
    Spikeinterface's `SortingExtractor`

    Parameters
    ----------
    sorting : BaseSorting
        The SortingExtractor object containing unit data.
    nwbfile : pynwb.NWBFile, optional
        The NWBFile object to write the unit data into.
    unit_ids : list of int or str, optional
        The specific unit IDs to write. If None, all units are written.
    property_descriptions : dict, optional
        Custom descriptions for unit properties. Keys should match property names in `sorting`,
        and values will be used as descriptions in the Units table.
    skip_properties : list of str, optional
        Unit properties to exclude from writing.

    write_as : {'units', 'processing'}, default: 'units'
        Where to write the unit data:
            - 'units': Write to the primary NWBFile.units table.
            - 'processing': Write to the processing module (intermediate data).
    units_name : str, default: 'units'
        Name of the Units table. Must be 'units' if `write_as` is 'units'.
    units_description : str, optional
        Description for the Units table (e.g., sorting method, curation details).
    waveform_means : np.ndarray, optional
        Waveform mean (template) for each unit. Shape: (num_units, num_samples, num_channels).
    waveform_sds : np.ndarray, optional
        Waveform standard deviation for each unit. Shape: (num_units, num_samples, num_channels).
    unit_electrode_indices : list of lists of int, optional
        A list of lists of integers indicating the indices of the electrodes that each unit is associated with.
        The length of the list must match the number of units in the sorting extractor.
    null_values_for_properties : dict of str to Any
        A dictionary mapping properties to their respective default values. If a property is not found in this
        dictionary, a sensible default value based on the type of `sample_data` will be used.
    """

    assert write_as in [
        "units",
        "processing",
    ], f"Argument write_as ({write_as}) should be one of 'units' or 'processing'!"
    write_in_processing_module = False if write_as == "units" else True

    _add_units_table_to_nwbfile(
        sorting=sorting,
        unit_ids=unit_ids,
        nwbfile=nwbfile,
        property_descriptions=property_descriptions,
        skip_properties=skip_properties,
        write_in_processing_module=write_in_processing_module,
        units_table_name=units_name,
        unit_table_description=units_description,
        waveform_means=waveform_means,
        waveform_sds=waveform_sds,
        unit_electrode_indices=unit_electrode_indices,
        null_values_for_properties=null_values_for_properties,
    )


def add_electrical_series_to_nwbfile(
    recording: BaseRecording,
    nwbfile: pynwb.NWBFile,
    metadata: dict = None,
    segment_index: int = 0,
    write_as: Literal["raw", "processed", "lfp"] = "raw",
    es_key: str = None,
    write_scaled: bool = False,
    iterator_type: str | None = "v2",
    iterator_opts: dict | None = None,
    always_write_timestamps: bool = False,
):
    """
    Deprecated. Call `add_recording_to_nwbfile` instead.
    """

    warnings.warn(
        "This function is deprecated and will be removed in or October 2025. "
        "Use the 'add_recording_to_nwbfile' function instead.",
        DeprecationWarning,
    )

    _add_recording_segment_to_nwbfile(
        recording=recording,
        nwbfile=nwbfile,
        segment_index=segment_index,
        metadata=metadata,
        write_as=write_as,
        es_key=es_key,
        write_scaled=write_scaled,
        iterator_type=iterator_type,
        iterator_opts=iterator_opts,
        always_write_timestamps=always_write_timestamps,
    )


def _add_recording_segment_to_nwbfile(
    recording: BaseRecording,
    nwbfile: pynwb.NWBFile,
    metadata: dict = None,
    segment_index: int = 0,
    write_as: Literal["raw", "processed", "lfp"] = "raw",
    es_key: str = None,
    write_scaled: bool = False,
    iterator_type: str | None = "v2",
    iterator_opts: dict | None = None,
    always_write_timestamps: bool = False,
):
    """
    See add_recording_to_nwbfile for details.
    """

    if write_scaled:
        warnings.warn(
            "The 'write_scaled' parameter is deprecated and will be removed in October 2025. "
            "The function will automatically handle channel conversion and offsets using "
            "'gain_to_physical_unit' and 'offset_to_physical_unit' properties.",
            DeprecationWarning,
            stacklevel=2,
        )

    assert write_as in [
        "raw",
        "processed",
        "lfp",
    ], f"'write_as' should be 'raw', 'processed' or 'lfp', but instead received value {write_as}"

    modality_signature = write_as.upper() if write_as == "lfp" else write_as.capitalize()
    default_name = f"ElectricalSeries{modality_signature}"
    default_description = dict(raw="Raw acquired data", lfp="Processed data - LFP", processed="Processed data")

    eseries_kwargs = dict(name=default_name, description=default_description[write_as])

    # Select and/or create module if lfp or processed data is to be stored.
    if write_as in ["lfp", "processed"]:
        ecephys_mod = get_module(
            nwbfile=nwbfile,
            name="ecephys",
            description="Intermediate data from extracellular electrophysiology recordings, e.g., LFP.",
        )
        if write_as == "lfp" and "LFP" not in ecephys_mod.data_interfaces:
            ecephys_mod.add(pynwb.ecephys.LFP(name="LFP"))
        if write_as == "processed" and "Processed" not in ecephys_mod.data_interfaces:
            ecephys_mod.add(pynwb.ecephys.FilteredEphys(name="Processed"))

    if metadata is not None and "Ecephys" in metadata and es_key is not None:
        assert es_key in metadata["Ecephys"], f"metadata['Ecephys'] dictionary does not contain key '{es_key}'"
        eseries_kwargs.update(metadata["Ecephys"][es_key])

    # If the recording extractor has more than 1 segment, append numbers to the names so that the names are unique.
    # 0-pad these names based on the number of segments.
    # If there are 10 segments use 2 digits, if there are 100 segments use 3 digits, etc.
    if recording.get_num_segments() > 1:
        width = int(np.ceil(np.log10((recording.get_num_segments()))))
        eseries_kwargs["name"] += f"{segment_index:0{width}}"

    # The add_electrodes adds a column with channel name to the electrode table.
    add_electrodes_to_nwbfile(recording=recording, nwbfile=nwbfile, metadata=metadata)

    # Create a region for the electrodes table by matching recording channels to table rows
    channel_map = _build_channel_id_to_electrodes_table_map(recording=recording, nwbfile=nwbfile)
    channel_ids = recording.get_channel_ids()
    electrode_table_indices = [channel_map[channel_id] for channel_id in channel_ids]
    electrode_table_region = nwbfile.create_electrode_table_region(
        region=electrode_table_indices,
        description="electrode_table_region",
    )
    eseries_kwargs.update(electrodes=electrode_table_region)

    if recording.has_scaleable_traces():
        # Spikeinterface gains and offsets are gains and offsets to micro volts.
        # The units of the ElectricalSeries should be volts so we scale correspondingly.
        micro_to_volts_conversion_factor = 1e-6
        channel_gains_to_volts = recording.get_channel_gains() * micro_to_volts_conversion_factor
        channel_offsets_to_volts = recording.get_channel_offsets() * micro_to_volts_conversion_factor

        unique_gains = set(channel_gains_to_volts)
        if len(unique_gains) == 1:
            conversion_to_volts = channel_gains_to_volts[0]
            eseries_kwargs.update(conversion=conversion_to_volts)
        else:
            eseries_kwargs.update(channel_conversion=channel_gains_to_volts)

        unique_offset = set(channel_offsets_to_volts)
        if len(unique_offset) > 1:
            channel_ids = recording.get_channel_ids()
            # This prints a user friendly error where the user is provided with a map from offset to channels
            _report_variable_offset(recording=recording)

        unique_offset = channel_offsets_to_volts[0]
        eseries_kwargs.update(offset=unique_offset)
    else:
        warning_message = (
            "The recording extractor does not have gains and offsets to convert to volts. "
            "That means that correct units are not guaranteed.  \n"
            "Set the correct gains and offsets to the recording extractor before writing to NWB."
        )
        warnings.warn(warning_message, UserWarning, stacklevel=2)

    # Iterator
    ephys_data_iterator = _recording_traces_to_hdmf_iterator(
        recording=recording,
        segment_index=segment_index,
        iterator_type=iterator_type,
        iterator_opts=iterator_opts,
    )
    eseries_kwargs.update(data=ephys_data_iterator)

    if always_write_timestamps:
        timestamps = recording.get_times(segment_index=segment_index)
        eseries_kwargs.update(timestamps=timestamps)
    else:
        # By default we write the rate if the timestamps are regular
        recording_has_timestamps = recording.has_time_vector(segment_index=segment_index)
        if recording_has_timestamps:
            timestamps = recording.get_times(segment_index=segment_index)
            rate = calculate_regular_series_rate(series=timestamps)  # Returns None if it is not regular
            recording_t_start = timestamps[0]
        else:
            rate = recording.get_sampling_frequency()
            recording_t_start = recording._recording_segments[segment_index].t_start or 0

        if rate:
            starting_time = float(recording_t_start)
            # Note that we call the sampling frequency again because the estimated rate might be different from the
            # sampling frequency of the recording extractor by some epsilon.
            eseries_kwargs.update(starting_time=starting_time, rate=recording.get_sampling_frequency())
        else:
            eseries_kwargs.update(timestamps=timestamps)

    # Create ElectricalSeries object and add it to nwbfile
    es = pynwb.ecephys.ElectricalSeries(**eseries_kwargs)
    if write_as == "raw":
        nwbfile.add_acquisition(es)
    elif write_as == "processed":
        ecephys_mod.data_interfaces["Processed"].add_electrical_series(es)
    elif write_as == "lfp":
        ecephys_mod.data_interfaces["LFP"].add_electrical_series(es)


def _get_default_ecephys_metadata():
    """
    Returns fresh ecephys default metadata dictionary.

    Single source of truth for all ecephys default metadata.
    Structure matches the output of recording interfaces and extractor functions.
    Each call returns a new instance to prevent accidental mutation of global state.
    """
    from neuroconv.tools.nwb_helpers import get_default_nwbfile_metadata

    metadata = get_default_nwbfile_metadata()

    metadata["Ecephys"] = {
        "Device": [{"name": "Device", "description": "Ecephys probe. Automatically generated."}],
        "ElectrodeGroup": [
            {"name": "ElectrodeGroup", "description": "no description", "location": "unknown", "device": "Device"}
        ],
        "ElectricalSeries": {"name": "ElectricalSeries", "description": "Acquisition traces for the ElectricalSeries."},
    }

    return metadata


def add_devices_to_nwbfile(nwbfile: pynwb.NWBFile, metadata: DeepDict | None = None):
    """
    Add device information to nwbfile object.

    Will always ensure nwbfile has at least one device, but multiple
    devices within the metadata list will also be created.

    Parameters
    ----------
    nwbfile: NWBFile
        nwb file to which the recording information is to be added
    metadata: DeepDict
        metadata info for constructing the nwb file (optional).
        Should be of the format::

            metadata['Ecephys']['Device'] = [
                {
                    'name': my_name,
                    'description': my_description
                },
                ...
            ]

        Missing keys in an element of metadata['Ecephys']['Device'] will be auto-populated with defaults.
    """
    if nwbfile is not None:
        assert isinstance(nwbfile, pynwb.NWBFile), "'nwbfile' should be of type pynwb.NWBFile"

    # Get default device metadata from single source of truth
    ecephys_defaults = _get_default_ecephys_metadata()
    defaults = ecephys_defaults["Ecephys"]["Device"][0]

    if metadata is None:
        metadata = dict()
    if "Ecephys" not in metadata:
        metadata["Ecephys"] = dict()
    if "Device" not in metadata["Ecephys"]:
        metadata["Ecephys"]["Device"] = [defaults]
    for device_metadata in metadata["Ecephys"]["Device"]:
        if device_metadata.get("name", defaults["name"]) not in nwbfile.devices:
            device_kwargs = dict(defaults, **device_metadata)
            nwbfile.create_device(**device_kwargs)


def add_electrode_groups_to_nwbfile(recording: BaseRecording, nwbfile: pynwb.NWBFile, metadata: dict | None = None):
    """
    Deprecated. This will become a private method.
    """
    warnings.warn("This function is deprecated and will be removed in future versions.", DeprecationWarning)

    _add_electrode_groups_to_nwbfile(recording=recording, nwbfile=nwbfile, metadata=metadata)


def _add_electrode_groups_to_nwbfile(recording: BaseRecording, nwbfile: pynwb.NWBFile, metadata: dict | None = None):
    """
    Add electrode group information to nwbfile object.

    Will always ensure nwbfile has at least one electrode group.
    Will auto-generate a linked device if the specified name does not exist in the nwbfile.

    Parameters
    ----------
    recording: spikeinterface.BaseRecording
    nwbfile: pynwb.NWBFile
        nwb file to which the recording information is to be added
    metadata: dict
        metadata info for constructing the nwb file (optional).
        Should be of the format::

            metadata['Ecephys']['ElectrodeGroup'] = [
                {
                    'name': my_name,
                    'description': my_description,
                    'location': electrode_location,
                    'device': my_device_name
                },
                ...
            ]

        Missing keys in an element of ``metadata['Ecephys']['ElectrodeGroup']`` will be auto-populated with defaults.
        Group names set by RecordingExtractor channel properties will also be included with passed metadata,
        but will only use default description and location.
    """
    assert isinstance(nwbfile, pynwb.NWBFile), "'nwbfile' should be of type pynwb.NWBFile"

    if metadata is None:
        metadata = dict()
    if "Ecephys" not in metadata:
        metadata["Ecephys"] = dict()

    add_devices_to_nwbfile(nwbfile=nwbfile, metadata=metadata)

    group_names = _get_group_name(recording=recording)

    # Get default electrode group metadata from single source of truth
    ecephys_defaults = _get_default_ecephys_metadata()
    default_electrode_group = ecephys_defaults["Ecephys"]["ElectrodeGroup"][0]

    defaults = [
        dict(
            name=group_name,
            description=default_electrode_group["description"],
            location=default_electrode_group["location"],
            device=[i.name for i in nwbfile.devices.values()][0],
        )
        for group_name in group_names
    ]

    if "ElectrodeGroup" not in metadata["Ecephys"]:
        metadata["Ecephys"]["ElectrodeGroup"] = defaults
    assert all(
        [isinstance(x, dict) for x in metadata["Ecephys"]["ElectrodeGroup"]]
    ), "Expected metadata['Ecephys']['ElectrodeGroup'] to be a list of dictionaries!"

    for group_metadata in metadata["Ecephys"]["ElectrodeGroup"]:
        if group_metadata.get("name", defaults[0]["name"]) not in nwbfile.electrode_groups:
            device_name = group_metadata.get("device", defaults[0]["device"])
            if device_name not in nwbfile.devices:
                new_device_metadata = dict(Ecephys=dict(Device=[dict(name=device_name)]))
                add_devices_to_nwbfile(nwbfile=nwbfile, metadata=new_device_metadata)
                warnings.warn(
                    f"Device '{device_name}' not detected in "
                    "attempted link to electrode group! Automatically generating."
                )
            electrode_group_kwargs = dict(defaults[0], **group_metadata)
            electrode_group_kwargs.update(device=nwbfile.devices[device_name])
            nwbfile.create_electrode_group(**electrode_group_kwargs)

    # TODO: Check this, probably not necessary
    if not nwbfile.electrode_groups:
        device_name = list(nwbfile.devices.keys())[0]
        device = nwbfile.devices[device_name]
        if len(nwbfile.devices) > 1:
            warnings.warn(
                "More than one device found when adding electrode group "
                f"via channel properties: using device '{device_name}'. To use a "
                "different device, indicate it the metadata argument."
            )
        electrode_group_kwargs = dict(defaults[0])
        electrode_group_kwargs.update(device=device)
        for group_name in np.unique(recording.get_channel_groups()).tolist():
            electrode_group_kwargs.update(name=str(group_name))
            nwbfile.create_electrode_group(**electrode_group_kwargs)


def _get_electrode_name(recording: BaseRecording) -> np.ndarray | None:
    """
    Extract electrode names from a recording when a probe is attached.

    The purpose of this auxiliary method is to unify electrode name extraction from a recording
    across the ecephys pipeline and neuroconv. This achieves consistency and avoids duplication of code.

    For recordings with attached probes (via ProbeInterface), electrode names are derived from
    probe contact identifiers. These represent physical electrodes, allowing multiple channels
    (e.g., AP and LF bands in neuropixel) from the same electrode to be properly grouped.

    When available, we use the electrode_name property. If not available but a probe is attached,
    we extract contact_ids from the probe. Otherwise, we return None to indicate no probe-based
    electrode information is available.

    Parameters
    ----------
    recording : BaseRecording
        The recording object from which to extract electrode names.

    Returns
    -------
    np.ndarray | None
        An array containing electrode names if available from the recording property or probe.
        Returns None if the recording has no electrode_name property and no probe attached.
    """
    # Check if recording has electrode_name property already set
    electrode_names = recording.get_property("electrode_name")
    if electrode_names is not None:
        return electrode_names

    # Try to get electrode names from probe contact_ids
    if recording.has_probe():
        # get_probegroup() works for both single and multiple probes
        probegroup = recording.get_probegroup()

        # Collect contact_ids from all probes
        all_contact_ids = []
        for probe in probegroup.probes:
            contact_ids = probe.contact_ids
            # contact_ids is None for microelectrode arrays (Biocam, Maxwell, MEArec) - this is valid in probeinterface
            # These formats have probes for geometry but rely on channel-based identification
            if contact_ids is not None:
                all_contact_ids.extend(contact_ids)

        if len(all_contact_ids) > 0:
            return np.array(all_contact_ids)

    # Return None if no electrode names available
    return None


def _get_channel_name(recording: BaseRecording) -> np.ndarray:
    """
    Extract channel names from a recording.

    The purpose of this auxiliary method is to unify channel name extraction from a recording
    across the ecephys pipeline and neuroconv. This achieves consistency and avoids duplication of code.

    Spike interface sometimes inherits channel names from neo, those are usually human
    readable names in comparison to channel ids that only serve the purpose of unique identification.

    When available, we use the channel names, otherwise we fallback to channel ids as strings.

    Parameters
    ----------
    recording : BaseRecording
        The recording object from which to extract the channel names.

    Returns
    -------
    np.ndarray
        An array containing the channel names. If the `channel_name` property is not
        available, the channel IDs as strings will be returned.
    """
    # Uses either the `channel_name` property or the channel ids as string otherwise
    channel_names = recording.get_property("channel_name")
    if channel_names is None:
        channel_names = recording.get_channel_ids().astype("str", copy=False)

    return channel_names


def _get_group_name(recording: BaseRecording) -> np.ndarray:
    """
    Extract the canonical `group_name` from the recording, which will be written
    in the electrodes table.

    Parameters
    ----------
    recording : BaseRecording
        The recording object from which to extract the group names.

    Returns
    -------
    np.ndarray
        An array containing the group names. If the `group_name` property is not
        available, the channel groups will be returned. If the group names are
        empty, a default value 'ElectrodeGroup' will be used.

    Raises
    ------
    ValueError
        If the number of unique group names doesn't match the number of unique groups,
        or if the mapping between group names and group numbers is inconsistent.
    """
    # Get default electrode group name from single source of truth
    ecephys_defaults = _get_default_ecephys_metadata()
    default_group_name = ecephys_defaults["Ecephys"]["ElectrodeGroup"][0]["name"]
    group_names = recording.get_property("group_name")
    groups = recording.get_channel_groups()

    if group_names is None:
        group_names = groups
    if group_names is None:
        group_names = np.full(recording.get_num_channels(), fill_value=default_group_name)

    # Always ensure group_names are strings
    group_names = group_names.astype("str", copy=False)

    # If for any reason the group names are empty, fill them with the default
    group_names[group_names == ""] = default_group_name

    # Validate group names against groups
    if groups is not None:
        unique_groups = set(groups)
        unique_names = set(group_names)

        if len(unique_names) != len(unique_groups):
            raise ValueError("The number of group names must match the number of groups")

        # Check consistency of group name to group number mapping
        group_to_name_map = {}
        for group, name in zip(groups, group_names):
            if group in group_to_name_map:
                if group_to_name_map[group] != name:
                    raise ValueError("Inconsistent mapping between group numbers and group names")
            else:
                group_to_name_map[group] = name

    return group_names


def _build_channel_id_to_electrodes_table_map(
    recording: BaseRecording, nwbfile: pynwb.NWBFile
) -> dict[str | int, int | None]:
    """
    Build a mapping from recording channel IDs to electrode table row indices.

    The purpose of this function is to work as a single source of truth for matching
    recordings with electrode table rows in NWB.

    The way that this works is that an element is fully identified by three fields:
    - group_name
    - electrode_name (if probe is attached)
    - channel_name

    We do the match in two passes, first for every row we build a virtual global id that has
    this format:
    {group_name}_{electrode_name}_{channel_name}

    Where the electrode_name is "" if no probe is attached.

    Then, to see to which row a channel belongs to, we build the same virtual id
    and we do a lookup in the table.

    **Matching Logic**:
    - If recording has probe → match by (group_name, electrode_name, channel_name)
    - If recording has no probe → match by (group_name, "", channel_name)

    Parameters
    ----------
    recording : BaseRecording
        The recording object whose channels need to be mapped.
    nwbfile : pynwb.NWBFile
        The NWBFile containing the electrode table.

    Returns
    -------
    dict[str | int, int | None]
        Dictionary mapping channel ID to electrode table row index.
        Value is None if the channel is not found in the table.
        Keys are channel IDs from recording.get_channel_ids().
    """
    num_channels = recording.get_num_channels()
    channel_ids = recording.get_channel_ids()

    # Initialize mapping with None (channel not in table)
    channel_to_electrode_row = defaultdict(lambda: None)

    # If no electrode table, all channels are unmapped
    if nwbfile.electrodes is None or len(nwbfile.electrodes) == 0:
        return {channel_id: None for channel_id in channel_ids}

    # Determine which columns exist in the table
    has_electrode_column = "electrode_name" in nwbfile.electrodes.colnames
    has_channel_column = "channel_name" in nwbfile.electrodes.colnames

    # Build lookup table from existing rows
    # Note: We check if columns exist before trying to access them
    table_lookup = {}
    for row_index in range(len(nwbfile.electrodes)):
        group = nwbfile.electrodes["group_name"][row_index]
        electrode = nwbfile.electrodes["electrode_name"][row_index] if has_electrode_column else ""
        channel = nwbfile.electrodes["channel_name"][row_index] if has_channel_column else ""
        virtual_id = f"{group}_{electrode}_{channel}"
        table_lookup[virtual_id] = row_index

    # When there is no probe id information, the field is populated with empty strings
    group_names = _get_group_name(recording=recording)
    electrode_names = _get_electrode_name(recording=recording)
    channel_names = _get_channel_name(recording=recording)

    # Use empty strings for electrode names when no probe is attached
    if electrode_names is None:
        electrode_names = [""] * num_channels

    for channel_id, group, electrode, channel in zip(channel_ids, group_names, electrode_names, channel_names):
        virtual_id = f"{group}_{electrode}_{channel}"
        channel_to_electrode_row[channel_id] = table_lookup.get(virtual_id, None)

    return dict(channel_to_electrode_row)


def _get_null_value_for_property(property: str, sample_data: Any, null_values_for_properties: dict[str, Any]) -> Any:
    """
    Retrieve the null value for a given property based on its data type or a provided mapping.

    Also performs type checking to ensure the default value matches the type of the existing data.

    Parameters
    ----------
    sample_data : Any
        The sample data for which the default value is being determined. This can be of any data type.
    null_values_for_properties : dict of str to Any
        A dictionary mapping properties to their respective default values. If a property is not found in this
        dictionary, a sensible default value based on the type of `sample_data` will be used.

    Returns
    -------
    Any
        The default value for the specified property. The type of the default value will match the type of `sample_data`
        or the type specified in `null_values_for_properties`.

    Raises
    ------
    ValueError
        If a sensible default value cannot be determined for the given property and data type, or if the type of the
        provided default value does not match the type of the existing data.

    """

    type_to_default_value = {list: [], np.ndarray: np.array(np.nan), str: "", float: np.nan, complex: np.nan}

    # Check for numpy scalar types
    sample_data = sample_data.item() if isinstance(sample_data, np.generic) else sample_data

    default_value = null_values_for_properties.get(property, None)

    if default_value is None:
        sample_data_type = type(sample_data)
        default_value = type_to_default_value.get(sample_data_type, None)
        if default_value is None:
            error_msg = (
                f"Could not find a sensible default value for property '{property}' of type {sample_data_type} \n"
                "This can be fixed by  by modifying the recording property or setting a sensible default value "
                "using the `add_electrodes` function argument `null_values_for_properties` as in: \n"
                "null_values_for_properties = {{property}': default_value}"
            )
            raise ValueError(error_msg)
        if type(default_value) != sample_data_type:
            error_msg = (
                f"Default value for property '{property}' in null_values_for_properties dict has a "
                f"different type {type(default_value)} than the currently existing data type {sample_data_type}. \n"
                "Modify the recording property or the default value to match"
            )
            raise ValueError(error_msg)

    return default_value


def add_electrodes_to_nwbfile(
    recording: BaseRecording,
    nwbfile: pynwb.NWBFile,
    metadata: dict | None = None,
    exclude: tuple = (),
    null_values_for_properties: dict | None = None,
):
    """
    Build an electrode_table from the recording information and it to the nwbfile object.

    Parameters
    ----------
    recording: spikeinterface.BaseRecording
    nwbfile: NWBFile
        nwb file to which the recording information is to be added
    metadata: dict
        metadata info for constructing the nwb file (optional).
        Should be of the format::

            metadata['Ecephys']['Electrodes'] = [
                {
                    'name': my_name,
                    'description': my_description
                },
                ...
            ]

        Note that data intended to be added to the electrodes table of the NWBFile should be set as channel
        properties in the RecordingExtractor object.
        Missing keys in an element of metadata['Ecephys']['ElectrodeGroup'] will be auto-populated with defaults
        whenever possible.
        If 'my_name' is set to one of the required fields for nwbfile
        electrodes (id, x, y, z, imp, location, filtering, group_name),
        then the metadata will override their default values.
        Setting 'my_name' to metadata field 'group' is not supported as the linking to
        nwbfile.electrode_groups is handled automatically; please specify the string 'group_name' in this case.
        If no group information is passed via metadata, automatic linking to existing electrode groups,
        possibly including the default, will occur.
    exclude: tuple
        An iterable containing the string names of channel properties in the RecordingExtractor
        object to ignore when writing to the NWBFile.
    null_values_for_properties : dict of str to Any
        A dictionary mapping properties to their respective default values. If a property is not found in this
        dictionary, a sensible default value based on the type of `sample_data` will be used.
    """
    assert isinstance(
        nwbfile, pynwb.NWBFile
    ), f"'nwbfile' should be of type pynwb.NWBFile but is of type {type(nwbfile)}"

    null_values_for_properties = dict() if null_values_for_properties is None else null_values_for_properties

    # Test that metadata has the expected structure
    electrodes_metadata = list()
    if metadata is not None:
        electrodes_metadata = metadata.get("Ecephys", dict()).get("Electrodes", list())

    required_keys = {"name", "description"}
    assert all(
        [isinstance(property, dict) and set(property.keys()) == required_keys for property in electrodes_metadata]
    ), (
        "Expected metadata['Ecephys']['Electrodes'] to be a list of dictionaries, "
        "containing the keys 'name' and 'description'"
    )

    assert all(
        [property["name"] != "group" for property in electrodes_metadata]
    ), "The recording property 'group' is not allowed; please use 'group_name' instead!"

    # Transform to a dict that maps property name to its description
    property_descriptions = dict()
    for property in electrodes_metadata:
        property_descriptions[property["name"]] = property["description"]

    # 1. Build columns details from extractor properties: dict(name: dict(description='',data=data, index=False))
    data_to_add = dict()

    recording_properties = recording.get_property_keys()
    spikeinterface_special_cases = [
        "offset_to_uV",  # Written in the ElectricalSeries
        "gain_to_uV",  # Written in the ElectricalSeries
        "gain_to_physical_unit",  # Written in the ElectricalSeries
        "offset_to_physical_unit",  # Written in the ElectricalSeries
        "physical_unit",  # Written in the ElectricalSeries
        "contact_vector",  # Structured array representing the probe
        "channel_name",  # We handle this here with _get_channel_name
        "channel_names",  # Some formats from neo also have this property, skip it
        "group_name",  # We handle this here _get_group_name
        "group",  # We handle this here with _get_group_name
    ]
    excluded_properties = list(exclude) + spikeinterface_special_cases
    properties_to_extract = [property for property in recording_properties if property not in excluded_properties]

    for property in properties_to_extract:
        data = np.asarray(recording.get_property(property)).copy()  # Do not modify properties of the recording

        index = isinstance(data[0], (list, np.ndarray, tuple))
        if index and isinstance(data[0], np.ndarray):
            index = data[0].ndim

        # Fill with provided custom descriptions
        description = property_descriptions.get(property, "no description")
        data_to_add[property] = dict(description=description, data=data, index=index)

    # Special cases properties
    group_names = _get_group_name(recording=recording)
    electrode_names = _get_electrode_name(recording=recording)
    channel_names = _get_channel_name(recording=recording)

    # Always write channel_name column
    data_to_add["channel_name"] = dict(description="unique channel reference", data=channel_names, index=False)

    # Write electrode_name column when probe is attached
    if electrode_names is not None:
        data_to_add["electrode_name"] = dict(
            description="unique electrode reference from probe contact identifiers", data=electrode_names, index=False
        )

    data_to_add["group_name"] = dict(description="group_name", data=group_names, index=False)

    # Location in spikeinterface is equivalent to rel_x, rel_y, rel_z in the nwb standard
    if "location" in data_to_add:
        data = data_to_add["location"]["data"]
        column_number_to_property = {0: "rel_x", 1: "rel_y", 2: "rel_z"}
        for column_number in range(data.shape[1]):
            property = column_number_to_property[column_number]
            data_to_add[property] = dict(description=property, data=data[:, column_number], index=False)
        data_to_add.pop("location")

    # In the electrode table location is the brain area of spikeinterface
    if "brain_area" in data_to_add:
        data_to_add["location"] = data_to_add["brain_area"]
        data_to_add["location"].update(description="location")
        data_to_add.pop("brain_area")
    else:
        default_location = _get_default_ecephys_metadata()["Ecephys"]["ElectrodeGroup"][0]["location"]
        data = np.full(recording.get_num_channels(), fill_value=default_location)
        data_to_add["location"] = dict(description="location", data=data, index=False)

    # Add missing groups to the nwb file
    groupless_names = [group_name for group_name in group_names if group_name not in nwbfile.electrode_groups]
    if len(groupless_names) > 0:
        electrode_group_list = [dict(name=group_name) for group_name in groupless_names]
        missing_group_metadata = dict(Ecephys=dict(ElectrodeGroup=electrode_group_list))
        _add_electrode_groups_to_nwbfile(recording=recording, nwbfile=nwbfile, metadata=missing_group_metadata)

    group_list = [nwbfile.electrode_groups[group_name] for group_name in group_names]
    data_to_add["group"] = dict(description="the ElectrodeGroup object", data=group_list, index=False)

    schema_properties = {"group", "group_name", "location"}
    properties_to_add = set(data_to_add)
    electrode_table_previous_properties = set(nwbfile.electrodes.colnames) if nwbfile.electrodes else set()

    # The schema properties are always added by rows because they are required
    properties_to_add_by_rows = schema_properties.union(electrode_table_previous_properties)
    properties_to_add_by_columns = properties_to_add.difference(properties_to_add_by_rows)

    # Properties that were added before require null values to add by rows if data is missing
    properties_requiring_null_values = electrode_table_previous_properties.difference(properties_to_add)
    nul_values_for_rows = dict()
    for property in properties_requiring_null_values:
        sample_data = nwbfile.electrodes[property][:][0]
        null_value = _get_null_value_for_property(
            property=property,
            sample_data=sample_data,
            null_values_for_properties=null_values_for_properties,
        )
        nul_values_for_rows[property] = null_value

    # We only add new electrodes to the table
    # Use the mapping function to determine which channels are already in the table
    channel_map = _build_channel_id_to_electrodes_table_map(recording=recording, nwbfile=nwbfile)

    # Channels to add are those that don't have a row mapping (None)
    channel_ids_to_add = [channel_id for channel_id, row in channel_map.items() if row is None]

    # Create mapping from channel_id to channel_index for data array access
    channel_ids = recording.get_channel_ids()
    channel_id_to_index = {channel_id: index for index, channel_id in enumerate(channel_ids)}

    properties_with_data = properties_to_add_by_rows.intersection(data_to_add)
    for channel_id in channel_ids_to_add:
        channel_index = channel_id_to_index[channel_id]
        electrode_kwargs = nul_values_for_rows
        data_dict = {property: data_to_add[property]["data"][channel_index] for property in properties_with_data}
        electrode_kwargs.update(**data_dict)
        nwbfile.add_electrode(**electrode_kwargs, enforce_unique_id=True)

    # The channel_name/electrode_name column as we use it with group_name as a unique identifier
    # We fill previously inexistent values with the electrode table ids
    electrode_table_size = len(nwbfile.electrodes.id[:])
    num_channels_added = len(channel_ids_to_add)
    previous_table_size = electrode_table_size - num_channels_added

    # Handle channel_name and electrode_name columns (both may be present for probe-based recordings)
    if "channel_name" in properties_to_add_by_columns:
        cols_args = data_to_add["channel_name"]
        data = cols_args["data"]

        previous_ids = nwbfile.electrodes.id[:previous_table_size]
        default_value = np.array(previous_ids).astype("str")

        extended_data = np.hstack([default_value, data])
        cols_args["data"] = extended_data
        nwbfile.add_electrode_column("channel_name", **cols_args)

    if "electrode_name" in properties_to_add_by_columns:
        cols_args = data_to_add["electrode_name"]
        data = cols_args["data"]

        default_value = np.array([""] * previous_table_size)
        extended_data = np.hstack([default_value, data])
        cols_args["data"] = extended_data
        nwbfile.add_electrode_column("electrode_name", **cols_args)

    # Now find indices for this recording in the updated table
    # Rebuild the map after adding electrodes
    channel_map = _build_channel_id_to_electrodes_table_map(recording=recording, nwbfile=nwbfile)

    # Get indices where this recording's data goes (all should be found now)
    all_indices = np.arange(electrode_table_size)
    channel_ids = recording.get_channel_ids()
    indices_for_new_data = [channel_map[channel_id] for channel_id in channel_ids]
    indices_for_null_values = [index for index in all_indices if index not in indices_for_new_data]
    extending_column = len(indices_for_null_values) > 0

    # Add properties as columns (exclude channel_name and electrode_name as they were handled above)
    for property in properties_to_add_by_columns - {"channel_name", "electrode_name"}:
        cols_args = data_to_add[property]
        data = cols_args["data"]

        # This is the simple case, early return
        if not extending_column:
            nwbfile.add_electrode_column(property, **cols_args)
            continue

        adding_ragged_array = cols_args["index"]
        if not adding_ragged_array:
            sample_data = data[0]
            dtype = data.dtype
            extended_data = np.empty(shape=electrode_table_size, dtype=dtype)
            extended_data[indices_for_new_data] = data

            null_value = _get_null_value_for_property(
                property=property,
                sample_data=sample_data,
                null_values_for_properties=null_values_for_properties,
            )
            extended_data[indices_for_null_values] = null_value
        else:

            dtype = np.ndarray
            extended_data = np.empty(shape=electrode_table_size, dtype=dtype)
            for index, value in enumerate(data):
                index_in_extended_data = indices_for_new_data[index]
                index_in_extended_data = indices_for_new_data[index]
                extended_data[index_in_extended_data] = value.tolist()

            for index in indices_for_null_values:
                null_value = []
                extended_data[index] = null_value

        cols_args["data"] = extended_data
        nwbfile.add_electrode_column(property, **cols_args)


def check_if_recording_traces_fit_into_memory(recording: BaseRecording, segment_index: int = 0) -> None:
    """
    Deprecated. This function will no longer be exposed in the public API
    """

    warnings.warn(
        "This function is deprecated and will be removed in or October 2025. ",
        DeprecationWarning,
    )
    _check_if_recording_traces_fit_into_memory(recording=recording, segment_index=segment_index)


def _check_if_recording_traces_fit_into_memory(recording: BaseRecording, segment_index: int = 0) -> None:
    """
    Raises an error if the full traces of a recording extractor are larger than psutil.virtual_memory().available.

    Parameters
    ----------
    recording : spikeinterface.BaseRecording
        A recording extractor object from spikeinterface.
    segment_index : int, optional
        The segment index of the recording extractor object, by default 0

    Raises
    ------
    MemoryError
    """
    element_size_in_bytes = recording.get_dtype().itemsize
    num_channels = recording.get_num_channels()
    num_frames = recording.get_num_samples(segment_index=segment_index)

    traces_size_in_bytes = element_size_in_bytes * num_channels * num_frames
    available_memory_in_bytes = psutil.virtual_memory().available

    if traces_size_in_bytes > available_memory_in_bytes:
        message = (
            f"Memory error, full electrical series is {human_readable_size(traces_size_in_bytes, binary=True)} but only"
            f" {human_readable_size(available_memory_in_bytes, binary=True)} are available. Use iterator_type='V2'"
        )
        raise MemoryError(message)


def _recording_traces_to_hdmf_iterator(
    recording: BaseRecording,
    segment_index: int = None,
    return_scaled: bool = False,
    iterator_type: str | None = "v2",
    iterator_opts: dict = None,
) -> AbstractDataChunkIterator:
    """Function to wrap traces of spikeinterface recording into an AbstractDataChunkIterator.

    Parameters
    ----------
    recording : spikeinterface.BaseRecording
        A recording extractor from spikeinterface
    segment_index : int, optional
        The recording segment to add to the NWBFile.
    return_scaled : bool, defaults to False
        When True recording extractor objects from spikeinterface return their traces in microvolts.
    iterator_type: {"v2",  None}, default: 'v2'
        The type of DataChunkIterator to use.
        'v2' is the locally developed SpikeInterfaceRecordingDataChunkIterator, which offers full control over chunking.
        None: write the TimeSeries with no memory chunking.
    iterator_opts: dict, optional
        Dictionary of options for the iterator.
        See https://hdmf.readthedocs.io/en/stable/hdmf.data_utils.html#hdmf.data_utils.GenericDataChunkIterator
        for the full list of options.

    Returns
    -------
    traces_as_iterator: AbstractDataChunkIterator
        The traces of the recording extractor wrapped in an iterator object.

    Raises
    ------
    ValueError
        If the iterator_type is not 'v2' or None.
    """

    supported_iterator_types = ["v2", None]
    if iterator_type not in supported_iterator_types:
        message = f"iterator_type '{iterator_type}' is not supported. Must be either 'v2' (recommended) or None."
        raise ValueError(message)

    iterator_opts = dict() if iterator_opts is None else iterator_opts

    if iterator_type is None:
        _check_if_recording_traces_fit_into_memory(recording=recording, segment_index=segment_index)
        traces_as_iterator = recording.get_traces(return_scaled=return_scaled, segment_index=segment_index)
    elif iterator_type == "v2":
        traces_as_iterator = SpikeInterfaceRecordingDataChunkIterator(
            recording=recording,
            segment_index=segment_index,
            return_scaled=return_scaled,
            **iterator_opts,
        )
    else:
        raise ValueError("iterator_type must be None or 'v2'.")

    return traces_as_iterator


def _report_variable_offset(recording: BaseRecording) -> None:
    """
    Helper function to report variable offsets per channel IDs.
    Groups the different available offsets per channel IDs and raises a ValueError.
    """
    channel_offsets = recording.get_channel_offsets()
    channel_ids = recording.get_channel_ids()

    # Group the different offsets per channel IDs
    offset_to_channel_ids = {}
    for offset, channel_id in zip(channel_offsets, channel_ids):
        offset = offset.item() if isinstance(offset, np.generic) else offset
        channel_id = channel_id.item() if isinstance(channel_id, np.generic) else channel_id
        if offset not in offset_to_channel_ids:
            offset_to_channel_ids[offset] = []
        offset_to_channel_ids[offset].append(channel_id)

    # Create a user-friendly message
    message_lines = ["Recording extractors with heterogeneous offsets are not supported."]
    message_lines.append("Multiple offsets were found per channel IDs:")
    for offset, ids in offset_to_channel_ids.items():
        message_lines.append(f"  Offset {offset}: Channel IDs {ids}")
    message = "\n".join(message_lines)

    raise ValueError(message)


def add_recording_as_time_series_to_nwbfile(
    recording: BaseRecording,
    nwbfile: pynwb.NWBFile,
    metadata: dict | None = None,
    iterator_type: str | None = "v2",
    iterator_opts: dict | None = None,
    always_write_timestamps: bool = False,
    time_series_name: Optional[str] = None,
    metadata_key: str = "TimeSeries",
):
    """
    Adds traces from recording object as TimeSeries to an NWBFile object.

    Parameters
    ----------
    recording : BaseRecording
        A recording extractor from spikeinterface
    nwbfile : NWBFile
        nwb file to which the recording information is to be added
    metadata : dict, optional
        metadata info for constructing the nwb file.
        Should be of the format::

            metadata['TimeSeries'] = {
                'metadata_key': {
                    "name": "my_name",
                    'description': 'my_description',
                    'unit': 'my_unit',
                    "offset": offset_to_unit_value,
                    "conversion": gain_to_unit_value,
                    'comments': 'comments',
                    ...
                }
            }
        Where the metadata_key is used to look up metadata in the metadata dictionary.
    metadata_key: str
        The entry in TimeSeries metadata to use.
    iterator_type: {"v2",  None}, default: 'v2'
        The type of DataChunkIterator to use.
        'v2' is the locally developed SpikeInterfaceRecordingDataChunkIterator, which offers full control over chunking.
        None: write the TimeSeries with no memory chunking.
    iterator_opts: dict, optional
        Dictionary of options for the iterator.
        See https://hdmf.readthedocs.io/en/stable/hdmf.data_utils.html#hdmf.data_utils.GenericDataChunkIterator
        for the full list of options.
    always_write_timestamps : bool, default: False
        Set to True to always write timestamps.
        By default (False), the function checks if the timestamps are uniformly sampled, and if so, stores the data
        using a regular sampling rate instead of explicit timestamps. If set to True, timestamps will be written
        explicitly, regardless of whether the sampling rate is uniform.
    """
    if time_series_name is not None:
        warnings.warn(
            "The 'time_series_name' parameter is deprecated and will be removed in or after February 2026. "
            "Use 'metadata_key' to specify the metadata entry instead.",
            DeprecationWarning,
            stacklevel=2,
        )
    num_segments = recording.get_num_segments()
    for segment_index in range(num_segments):
        _add_time_series_segment_to_nwbfile(
            recording=recording,
            nwbfile=nwbfile,
            metadata=metadata,
            segment_index=segment_index,
            iterator_type=iterator_type,
            iterator_opts=iterator_opts,
            always_write_timestamps=always_write_timestamps,
            time_series_name=time_series_name,
            metadata_key=metadata_key,
        )


def _add_time_series_segment_to_nwbfile(
    recording: BaseRecording,
    nwbfile: pynwb.NWBFile,
    metadata: dict | None = None,
    segment_index: int = 0,
    iterator_type: str | None = "v2",
    iterator_opts: dict | None = None,
    always_write_timestamps: bool = False,
    time_series_name: Optional[str] = None,
    metadata_key: str = "time_series_metadata_key",
):
    """
    See `add_recording_as_time_series_to_nwbfile` for details.
    """

    # For backwards compatibility
    metadata_key = time_series_name or metadata_key
    metadata = DeepDict() if metadata is None else metadata

    time_series_name = time_series_name or metadata["TimeSeries"][metadata_key].get("name", "TimeSeries")
    tseries_kwargs = dict(name=time_series_name)
    metadata = deepcopy(metadata)

    # Apply metadata if available
    if "TimeSeries" in metadata and metadata_key in metadata["TimeSeries"]:
        time_series_metadata = metadata["TimeSeries"][metadata_key]
        tseries_kwargs.update(time_series_metadata)

    # If the recording extractor has more than 1 segment, append numbers to the names so that the names are unique.
    # 0-pad these names based on the number of segments.
    # If there are 10 segments use 2 digits, if there are 100 segments use 3 digits, etc.
    if recording.get_num_segments() > 1:
        width = int(np.ceil(np.log10((recording.get_num_segments()))))
        tseries_kwargs["name"] += f"{segment_index:0{width}}"

    # metadata "unit" has priority over recording properties
    if "unit" not in tseries_kwargs:
        # Get physical units from recording properties
        units = recording.get_property("physical_unit")
        # Get gain and offset from recording properties
        gain_to_unit = recording.get_property("gain_to_physical_unit")
        offset_to_unit = recording.get_property("offset_to_physical_unit")

        channels_have_same_unit = len(set(units)) == 1 if units is not None else False
        channels_have_same_gain = len(set(gain_to_unit)) == 1 if gain_to_unit is not None else False
        channels_have_same_offest = len(set(offset_to_unit)) == 1 if offset_to_unit is not None else False

        save_scaling_info = channels_have_same_unit and channels_have_same_gain and channels_have_same_offest

        if save_scaling_info:
            tseries_kwargs.update(unit=units[0], conversion=gain_to_unit[0], offset=offset_to_unit[0])
        else:
            warning_msg = (
                "The recording extractor has heterogeneous units or is lacking scaling factors. "
                "The time series will be saved with unit 'n.a.' and the conversion factors will not be set. "
                "To fix this issue, either: "
                "1) Set the unit in the metadata['TimeSeries'][time_series_name]['unit'] field, or "
                "2) Set the `physical_unit`, `gain_to_physical_unit`, and `offset_to_physical_unit` properties "
                "on the recording object with consistent units across all channels. "
                f"Channel units: {units if units is not None else 'None'}, "
                f"gain available: {gain_to_unit is not None}, "
                f"offset available: {offset_to_unit is not None}"
            )
            warnings.warn(warning_msg, UserWarning, stacklevel=2)
            tseries_kwargs.update(unit="n.a.")

    # Iterator
    data_iterator = _recording_traces_to_hdmf_iterator(
        recording=recording,
        segment_index=segment_index,
        iterator_type=iterator_type,
        iterator_opts=iterator_opts,
    )
    tseries_kwargs.update(data=data_iterator)

    if always_write_timestamps:
        timestamps = recording.get_times(segment_index=segment_index)
        tseries_kwargs.update(timestamps=timestamps)
    else:
        # By default we write the rate if the timestamps are regular
        recording_has_timestamps = recording.has_time_vector(segment_index=segment_index)
        if recording_has_timestamps:
            timestamps = recording.get_times(segment_index=segment_index)
            rate = calculate_regular_series_rate(series=timestamps)  # Returns None if it is not regular
            recording_t_start = timestamps[0]
        else:
            rate = recording.get_sampling_frequency()
            recording_t_start = recording._recording_segments[segment_index].t_start or 0

        # Set starting time and rate or timestamps
        if rate:
            starting_time = float(recording_t_start)
            # Note that we call the sampling frequency again because the estimated rate might be different from the
            # sampling frequency of the recording extractor by some epsilon.
            tseries_kwargs.update(starting_time=starting_time, rate=recording.get_sampling_frequency())
        else:
            tseries_kwargs.update(timestamps=timestamps)

    # Create TimeSeries object and add it to nwbfile
    time_series = pynwb.base.TimeSeries(**tseries_kwargs)

    nwbfile.add_acquisition(time_series)


def add_recording_metadata_to_nwbfile(recording: BaseRecording, nwbfile: pynwb.NWBFile, metadata: dict = None):
    """
    Add device, electrode_groups, and electrodes info to the nwbfile.

    Parameters
    ----------
    recording : SpikeInterfaceRecording
    nwbfile : NWBFile
        NWB file to which the recording information is to be added
    metadata : dict, optional
        metadata info for constructing the nwb file.
        Should be of the format::

            metadata['Ecephys']['Electrodes'] = [
                {
                    'name': my_name,
                    'description': my_description
                },
                ...
            ]

        Note that data intended to be added to the electrodes table of the ``NWBFile`` should be set as channel
        properties in the ``RecordingExtractor`` object.
        Missing keys in an element of ``metadata['Ecephys']['ElectrodeGroup']`` will be auto-populated with defaults
        whenever possible.
        If ``'my_name'`` is set to one of the required fields for nwbfile
        electrodes (id, x, y, z, imp, location, filtering, group_name),
        then the metadata will override their default values.
        Setting ``'my_name'`` to metadata field ``'group'`` is not supported as the linking to
        ``nwbfile.electrode_groups`` is handled automatically; please specify the string ``'group_name'`` in this case.
        If no group information is passed via metadata, automatic linking to existing electrode groups,
        possibly including the default, will occur.
    """
    add_devices_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
    _add_electrode_groups_to_nwbfile(recording=recording, nwbfile=nwbfile, metadata=metadata)
    add_electrodes_to_nwbfile(recording=recording, nwbfile=nwbfile, metadata=metadata)


def add_electrodes_info_to_nwbfile(recording: BaseRecording, nwbfile: pynwb.NWBFile, metadata: dict = None):
    """
    Dreprecated use `add_recording_metadata_to_nwbfile` instead.
    """
    warnings.warn(
        "This function is deprecated and will be removed in or October 2025. "
        "Use the 'add_recording_metadata_to_nwbfile' function instead.",
        DeprecationWarning,
    )
    add_recording_metadata_to_nwbfile(recording=recording, nwbfile=nwbfile, metadata=metadata)


def write_recording_to_nwbfile(
    recording: BaseRecording,
    nwbfile_path: FilePath | None = None,
    nwbfile: pynwb.NWBFile | None = None,
    metadata: dict | None = None,
    overwrite: bool = False,
    verbose: bool = False,
    write_as: str | None = "raw",
    es_key: str | None = None,
    write_electrical_series: bool = True,
    write_scaled: bool = False,
    iterator_type: str | None = "v2",
    iterator_opts: dict | None = None,
) -> pynwb.NWBFile:
    """
    Primary method for writing a RecordingExtractor object to an NWBFile.

    Parameters
    ----------
    recording : spikeinterface.BaseRecording
    nwbfile_path : FilePath, optional
        Path for where to write or load (if overwrite=False) the NWBFile.
        If specified, the context will always write to this location.
    nwbfile : NWBFile, optional
        If passed, this function will fill the relevant fields within the NWBFile object.
        E.g., calling::

            write_recording(recording=my_recording_extractor, nwbfile=my_nwbfile)

        will result in the appropriate changes to the my_nwbfile object.
        If neither 'nwbfile_path' nor 'nwbfile' are specified, an NWBFile object will be automatically generated
        and returned by the function.
    metadata : dict, optional
        metadata info for constructing the nwb file (optional). Should be
        of the format::

            metadata['Ecephys'] = {
                'Device': [
                    {
                        'name': my_name,
                        'description': my_description
                    },
                    ...
                ]
                'ElectrodeGroup': [
                    {
                        'name': my_name,
                        'description': my_description,
                        'location': electrode_location,
                        'device': my_device_name
                    },
                    ...
                ]
                'Electrodes': [
                    {
                        'name': my_name,
                        'description': my_description
                    },
                    ...
                ]
                'ElectricalSeries' = {
                    'name': my_name,
                    'description': my_description
                }
        Note that data intended to be added to the electrodes table of the NWBFile should be set as channel
        properties in the RecordingExtractor object.
    overwrite : bool, default: False
        Whether to overwrite the NWBFile if one exists at the nwbfile_path.
    verbose : bool, default: False
        If 'nwbfile_path' is specified, informs user after a successful write operation.
    write_as: {'raw', 'processed', 'lfp'}, optional
        How to save the traces data in the nwb file.
        - 'raw' will save it in acquisition
        - 'processed' will save it as FilteredEphys, in a processing module
        - 'lfp' will save it as LFP, in a processing module
    es_key: str, optional
        Key in metadata dictionary containing metadata info for the specific electrical series
    write_electrical_series: bool, default: True
        If True, electrical series are written in acquisition. If False, only device, electrode_groups,
        and electrodes are written to NWB.
    write_scaled: bool, default: True
        If True, writes the scaled traces (return_scaled=True)
    iterator_type: {"v2",  None}
        The type of DataChunkIterator to use.
        'v2' is the locally developed SpikeInterfaceRecordingDataChunkIterator, which offers full control over chunking.
        None: write the TimeSeries with no memory chunking.
    iterator_opts: dict, optional
        Dictionary of options for the RecordingExtractorDataChunkIterator (iterator_type='v2').
        Valid options are:

        * buffer_gb : float, default: 1.0
            In units of GB. Recommended to be as much free RAM as available. Automatically calculates suitable
            buffer shape.
        * buffer_shape : tuple, optional
            Manual specification of buffer shape to return on each iteration.
            Must be a multiple of chunk_shape along each axis.
            Cannot be set if `buffer_gb` is specified.
        * chunk_mb : float. default: 1.0
            Should be below 1 MB. Automatically calculates suitable chunk shape.
        * chunk_shape : tuple, optional
            Manual specification of the internal chunk shape for the HDF5 dataset.
            Cannot be set if `chunk_mb` is also specified.
        * display_progress : bool, default: False
            Display a progress bar with iteration rate and estimated completion time.
        * progress_bar_options : dict, optional
            Dictionary of keyword arguments to be passed directly to tqdm.
            See https://github.com/tqdm/tqdm#parameters for options.
    """

    with make_or_load_nwbfile(
        nwbfile_path=nwbfile_path, nwbfile=nwbfile, metadata=metadata, overwrite=overwrite, verbose=verbose
    ) as nwbfile_out:
        add_recording_to_nwbfile(
            recording=recording,
            nwbfile=nwbfile_out,
            metadata=metadata,
            write_as=write_as,
            es_key=es_key,
            write_electrical_series=write_electrical_series,
            write_scaled=write_scaled,
            iterator_type=iterator_type,
            iterator_opts=iterator_opts,
        )
    return nwbfile_out


def add_units_table_to_nwbfile(
    sorting: BaseSorting,
    nwbfile: pynwb.NWBFile,
    unit_ids: list[str | int] | None = None,
    property_descriptions: dict | None = None,
    skip_properties: list[str] | None = None,
    units_table_name: str = "units",
    unit_table_description: str | None = None,
    write_in_processing_module: bool = False,
    waveform_means: np.ndarray | None = None,
    waveform_sds: np.ndarray | None = None,
    unit_electrode_indices: list[list[int]] | None = None,
    null_values_for_properties: dict | None = None,
):
    """
    add unist table will become a private method, use `add_sorting_to_nwbfile` instead.
    """

    warnings.warn(
        "This function is deprecated and will be removed in or after October 2025. "
        "Use the 'add_sorting_to_nwbfile' function instead.",
        DeprecationWarning,
    )
    _add_units_table_to_nwbfile(
        sorting=sorting,
        nwbfile=nwbfile,
        unit_ids=unit_ids,
        property_descriptions=property_descriptions,
        skip_properties=skip_properties,
        units_table_name=units_table_name,
        unit_table_description=unit_table_description,
        write_in_processing_module=write_in_processing_module,
        waveform_means=waveform_means,
        waveform_sds=waveform_sds,
        unit_electrode_indices=unit_electrode_indices,
        null_values_for_properties=null_values_for_properties,
    )


def _add_units_table_to_nwbfile(
    sorting: BaseSorting,
    nwbfile: pynwb.NWBFile,
    unit_ids: list[str | int] | None = None,
    property_descriptions: dict | None = None,
    skip_properties: list[str] | None = None,
    units_table_name: str = "units",
    unit_table_description: str | None = None,
    write_in_processing_module: bool = False,
    waveform_means: np.ndarray | None = None,
    waveform_sds: np.ndarray | None = None,
    unit_electrode_indices: list[list[int]] | None = None,
    null_values_for_properties: dict | None = None,
):
    """
    Add sorting data to a NWBFile object as a Units table.

    This function extracts unit properties from a SortingExtractor object and writes them
    to an NWBFile Units table, either in the primary units interface or the processing
    module (for intermediate/historical data). It handles unit selection, property customization,
    waveform data, and electrode mapping.

    Parameters
    ----------
    sorting : spikeinterface.BaseSorting
        The SortingExtractor object containing unit data.
    nwbfile : pynwb.NWBFile
        The NWBFile object to write the unit data into.
    unit_ids : list of int or str, optional
        The specific unit IDs to write. If None, all units are written.
    property_descriptions : dict, optional
        Custom descriptions for unit properties. Keys should match property names in `sorting`,
        and values will be used as descriptions in the Units table.
    skip_properties : list of str, optional
        Unit properties to exclude from writing.
    units_table_name : str, default: 'units'
        Name of the Units table. Must be 'units' if `write_in_processing_module` is False.
    unit_table_description : str, optional
        Description for the Units table (e.g., sorting method, curation details).
    write_in_processing_module : bool, default: False
        If True, write to the processing module (intermediate data). If False, write to
        the primary NWBFile.units table.
    waveform_means : np.ndarray, optional
        Waveform mean (template) for each unit. Shape: (num_units, num_samples, num_channels).
    waveform_sds : np.ndarray, optional
        Waveform standard deviation for each unit. Shape: (num_units, num_samples, num_channels).
    unit_electrode_indices : list of lists of int, optional
        A list of lists of integers indicating the indices of the electrodes that each unit is associated with.
        The length of the list must match the number of units in the sorting extractor.
    """
    unit_table_description = unit_table_description or "Autogenerated by neuroconv."

    assert isinstance(
        nwbfile, pynwb.NWBFile
    ), f"'nwbfile' should be of type pynwb.NWBFile but is of type {type(nwbfile)}"

    if unit_electrode_indices is not None:
        electrodes_table = nwbfile.electrodes
        if electrodes_table is None:
            raise ValueError(
                "Electrodes table is required to map units to electrodes. Add an electrode table to the NWBFile first."
            )

    null_values_for_properties = dict() if null_values_for_properties is None else null_values_for_properties

    if not write_in_processing_module and units_table_name != "units":
        raise ValueError("When writing to the nwbfile.units table, the name of the table must be 'units'!")

    if write_in_processing_module:
        ecephys_mod = get_module(
            nwbfile=nwbfile,
            name="ecephys",
            description="Intermediate data from extracellular electrophysiology recordings, e.g., LFP.",
        )
        write_table_first_time = units_table_name not in ecephys_mod.data_interfaces
        if write_table_first_time:
            units_table = pynwb.misc.Units(name=units_table_name, description=unit_table_description)
            ecephys_mod.add(units_table)

        units_table = ecephys_mod[units_table_name]
    else:
        write_table_first_time = nwbfile.units is None
        if write_table_first_time:
            nwbfile.units = pynwb.misc.Units(name="units", description=unit_table_description)
        units_table = nwbfile.units

    default_descriptions = dict(
        isi_violation="Quality metric that measures the ISI violation ratio as a proxy for the purity of the unit.",
        firing_rate="Number of spikes per unit of time.",
        template="The extracellular average waveform.",
        max_channel="The recording channel id with the largest amplitude.",
        halfwidth="The full-width half maximum of the negative peak computed on the maximum channel.",
        peak_to_valley="The duration between the negative and the positive peaks computed on the maximum channel.",
        snr="The signal-to-noise ratio of the unit.",
        quality="Quality of the unit as defined by phy (good, mua, noise).",
        spike_amplitude="Average amplitude of peaks detected on the channel.",
        spike_rate="Average rate of peaks detected on the channel.",
        unit_name="Unique reference for each unit.",
    )
    if property_descriptions is None:
        property_descriptions = dict()
    if skip_properties is None:
        skip_properties = list()

    property_descriptions = dict(default_descriptions, **property_descriptions)

    data_to_add = defaultdict(dict)
    sorting_properties = sorting.get_property_keys()
    excluded_properties = list(skip_properties) + ["contact_vector"]
    properties_to_extract = [property for property in sorting_properties if property not in excluded_properties]

    if unit_ids is not None:
        sorting = sorting.select_units(unit_ids=unit_ids)
        if unit_electrode_indices is not None:
            unit_electrode_indices = np.array(unit_electrode_indices)[sorting.ids_to_indices(unit_ids)]
    unit_ids = sorting.unit_ids

    # Extract properties
    for property in properties_to_extract:
        data = sorting.get_property(property)

        index = isinstance(data[0], (list, np.ndarray, tuple))
        if index and isinstance(data[0], np.ndarray):
            index = data[0].ndim

        description = property_descriptions.get(property, "No description.")
        data_to_add[property].update(description=description, data=data, index=index)
        if property in ["max_channel", "max_electrode"] and nwbfile.electrodes is not None:
            data_to_add[property].update(table=nwbfile.electrodes)

    # Unit name logic
    if "unit_name" in data_to_add:
        # if 'unit_name' is set as a property, it is used to override default unit_ids (and "id")
        unit_name_array = data_to_add["unit_name"]["data"]
    else:
        unit_name_array = unit_ids.astype("str", copy=False)
        data_to_add["unit_name"].update(description="Unique reference for each unit.", data=unit_name_array)

    units_table_previous_properties = set(units_table.colnames).difference({"spike_times"})
    properties_to_add = set(data_to_add)
    properties_to_add_by_rows = units_table_previous_properties.union({"id"})
    properties_to_add_by_columns = properties_to_add - properties_to_add_by_rows

    # Properties that were added before require null values to add by rows if data is missing
    properties_requiring_null_values = units_table_previous_properties.difference(properties_to_add)
    null_values_for_row = {}
    for property in properties_requiring_null_values - {"electrodes"}:  # TODO, fix electrodes
        sample_data = units_table[property][:][0]
        null_value = _get_null_value_for_property(
            property=property,
            sample_data=sample_data,
            null_values_for_properties=null_values_for_properties,
        )
        null_values_for_row[property] = null_value

    # Special case
    null_values_for_row["id"] = None

    # Add data by rows excluding the rows with previously added unit names
    unit_names_used_previously = []
    if "unit_name" in units_table_previous_properties:
        unit_names_used_previously = units_table["unit_name"].data
    has_electrodes_column = "electrodes" in units_table.colnames

    properties_with_data = {property for property in properties_to_add_by_rows if "data" in data_to_add[property]}
    rows_in_data = [index for index in range(sorting.get_num_units())]
    if not has_electrodes_column:
        rows_to_add = [index for index in rows_in_data if unit_name_array[index] not in unit_names_used_previously]
    else:
        rows_to_add = []
        for index in rows_in_data:
            if unit_name_array[index] not in unit_names_used_previously:
                rows_to_add.append(index)
            else:
                unit_name = unit_name_array[index]
                previous_electrodes = units_table[np.where(units_table["unit_name"][:] == unit_name)[0]].electrodes
                if list(previous_electrodes.values[0]) != list(unit_electrode_indices[index]):
                    rows_to_add.append(index)

    for row in rows_to_add:
        unit_kwargs = null_values_for_row
        for property in properties_with_data:
            unit_kwargs[property] = data_to_add[property]["data"][row]
        spike_times = []

        # Extract and concatenate the spike times from multiple segments
        for segment_index in range(sorting.get_num_segments()):
            segment_spike_times = sorting.get_unit_spike_train(
                unit_id=unit_ids[row], segment_index=segment_index, return_times=True
            )
            spike_times.append(segment_spike_times)
        spike_times = np.concatenate(spike_times)
        if waveform_means is not None:
            unit_kwargs["waveform_mean"] = waveform_means[row]
            if waveform_sds is not None:
                unit_kwargs["waveform_sd"] = waveform_sds[row]
        if unit_electrode_indices is not None:
            unit_kwargs["electrodes"] = unit_electrode_indices[row]

        units_table.add_unit(spike_times=spike_times, **unit_kwargs, enforce_unique_id=True)

    # Add unit_name as a column and fill previously existing rows with unit_name equal to str(ids)
    unit_table_size = len(units_table.id[:])
    previous_table_size = len(units_table.id[:]) - len(unit_name_array)
    if "unit_name" in properties_to_add_by_columns:
        cols_args = data_to_add["unit_name"]
        data = cols_args["data"]

        previous_ids = units_table.id[:previous_table_size]
        default_value = np.array(previous_ids).astype("str")

        extended_data = np.hstack([default_value, data])
        cols_args["data"] = extended_data
        units_table.add_column("unit_name", **cols_args)

    # Build  a channel name to electrode table index map
    table_df = units_table.to_dataframe().reset_index()
    unit_name_to_electrode_index = {
        unit_name: table_df.query(f"unit_name=='{unit_name}'").index[0] for unit_name in unit_name_array
    }

    indices_for_new_data = [unit_name_to_electrode_index[unit_name] for unit_name in unit_name_array]
    indices_for_null_values = table_df.index.difference(indices_for_new_data).values
    extending_column = len(indices_for_null_values) > 0

    # Add properties as columns
    for property in properties_to_add_by_columns - {"unit_name"}:
        cols_args = data_to_add[property]
        data = cols_args["data"]

        # This is the simple case, early return
        if not extending_column:
            units_table.add_column(property, **cols_args)
            continue

        # Extending the columns is done differently for ragged arrays
        adding_ragged_array = cols_args["index"]
        if not adding_ragged_array:
            sample_data = data[0]
            dtype = data.dtype
            extended_data = np.empty(shape=unit_table_size, dtype=dtype)
            extended_data[indices_for_new_data] = data

            null_value = _get_null_value_for_property(
                property=property,
                sample_data=sample_data,
                null_values_for_properties=null_values_for_properties,
            )
            extended_data[indices_for_null_values] = null_value
        else:

            dtype = np.ndarray
            extended_data = np.empty(shape=unit_table_size, dtype=dtype)
            for index, value in enumerate(data):
                index_in_extended_data = indices_for_new_data[index]
                extended_data[index_in_extended_data] = value.tolist()

            for index in indices_for_null_values:
                null_value = []
                extended_data[index] = null_value

        # Add the data
        cols_args["data"] = extended_data
        units_table.add_column(property, **cols_args)


def write_sorting_to_nwbfile(
    sorting: BaseSorting,
    nwbfile_path: FilePath | None = None,
    nwbfile: pynwb.NWBFile | None = None,
    metadata: dict | None = None,
    overwrite: bool = False,
    verbose: bool = False,
    unit_ids: list[str | int] | None = None,
    property_descriptions: dict | None = None,
    skip_properties: list[str] | None = None,
    write_as: Literal["units", "processing"] = "units",
    units_name: str = "units",
    units_description: str = "Autogenerated by neuroconv.",
    waveform_means: np.ndarray | None = None,
    waveform_sds: np.ndarray | None = None,
    unit_electrode_indices=None,
):
    """
    Primary method for writing a SortingExtractor object to an NWBFile.

    Parameters
    ----------
    sorting : spikeinterface.BaseSorting
    nwbfile_path : FilePath, optional
        Path for where to write or load (if overwrite=False) the NWBFile.
        If specified, the context will always write to this location.
    nwbfile : NWBFile, optional
        If passed, this function will fill the relevant fields within the NWBFile object.
        E.g., calling::

            write_recording(recording=my_recording_extractor, nwbfile=my_nwbfile)

        will result in the appropriate changes to the my_nwbfile object.
        If neither 'nwbfile_path' nor 'nwbfile' are specified, an NWBFile object will be automatically generated
        and returned by the function.
    metadata : dict, optional
        Metadata dictionary with information used to create the NWBFile when one does not exist or overwrite=True.
    overwrite : bool, default: False
        Whether to overwrite the NWBFile if one exists at the nwbfile_path.
        The default is False (append mode).
    verbose : bool, default: False
        If 'nwbfile_path' is specified, informs user after a successful write operation.
    unit_ids : list, optional
        Controls the unit_ids that will be written to the nwb file. If None (default), all
        units are written.
    property_descriptions : dict, optional
        For each key in this dictionary which matches the name of a unit
        property in sorting, adds the value as a description to that
        custom unit column.
    skip_properties : list of str, optional
        Each string in this list that matches a unit property will not be written to the NWBFile.
    write_as : {'units', 'processing'}
        How to save the units table in the nwb file. Options:
        - 'units' will save it to the official NWBFile.Units position; recommended only for the final form of the data.
        - 'processing' will save it to the processing module to serve as a historical provenance for the official table.
    units_name : str, default: 'units'
        The name of the units table. If write_as=='units', then units_name must also be 'units'.
    units_description : str, default: 'Autogenerated by neuroconv.'
    waveform_means : np.ndarray, optional
        Waveform mean (template) for each unit. Shape: (num_units, num_samples, num_channels).
    waveform_sds : np.ndarray, optional
        Waveform standard deviation for each unit. Shape: (num_units, num_samples, num_channels).
    unit_electrode_indices : list of lists of int, optional
        For each unit, a list of electrode indices corresponding to waveform data.
    """

    with make_or_load_nwbfile(
        nwbfile_path=nwbfile_path, nwbfile=nwbfile, metadata=metadata, overwrite=overwrite, verbose=verbose
    ) as nwbfile_out:
        add_sorting_to_nwbfile(
            sorting=sorting,
            nwbfile=nwbfile_out,
            unit_ids=unit_ids,
            property_descriptions=property_descriptions,
            skip_properties=skip_properties,
            write_as=write_as,
            units_name=units_name,
            units_description=units_description,
            waveform_means=waveform_means,
            waveform_sds=waveform_sds,
            unit_electrode_indices=unit_electrode_indices,
        )


def add_sorting_analyzer_to_nwbfile(
    sorting_analyzer: SortingAnalyzer,
    nwbfile: pynwb.NWBFile | None = None,
    metadata: dict | None = None,
    recording: BaseRecording | None = None,
    unit_ids: list[str] | list[int] | None = None,
    skip_properties: list[str] | None = None,
    property_descriptions: dict | None = None,
    write_as: Literal["units", "processing"] = "units",
    units_name: str = "units",
    units_description: str = "Autogenerated by neuroconv.",
):
    """
    Convenience function to write directly a sorting analyzer object to an nwbfile.

    The function adds the data of the recording and the sorting plus the following information from the sorting analyzer:
    - quality metrics
    - template mean and std
    - template metrics


    Parameters
    ----------
    sorting_analyzer : spikeinterface.SortingAnalyzer
        The sorting analyzer object to be written to the NWBFile.
    nwbfile : NWBFile, optional
        If passed, this function will fill the relevant fields within the NWBFile object.
        E.g., calling::

            write_recording(recording=my_recording_extractor, nwbfile=my_nwbfile)

        will result in the appropriate changes to the my_nwbfile object.
        If neither 'nwbfile_path' nor 'nwbfile' are specified, an NWBFile object will be automatically generated
        and returned by the function.
    metadata : dict, optional
        Metadata dictionary with information used to create the NWBFile when one does not exist or overwrite=True.
        The "Ecephys" section of metadata is also used to create electrodes and electrical series fields.
    recording : BaseRecording, optional
        If the sorting_analyzer is 'recordingless', this argument is required to save electrode info.
    unit_ids : list, optional
        Controls the unit_ids that will be written to the nwb file. If None (default), all
        units are written.
    property_descriptions : dict, optional
        For each key in this dictionary which matches the name of a unit
        property in sorting, adds the value as a description to that
        custom unit column.
    skip_properties : list of str, optional
        Each string in this list that matches a unit property will not be written to the NWBFile.
    write_as : {'units', 'processing'}
        How to save the units table in the nwb file. Options:
        - 'units' will save it to the official NWBFile.Units position; recommended only for the final form of the data.
        - 'processing' will save it to the processing module to serve as a historical provenance for the official table.
    units_name : str, optional, default: 'units'
        The name of the units table. If write_as=='units', then units_name must also be 'units'.
    units_description : str, default: 'Autogenerated by neuroconv.'
    """

    # TODO: move into add_units
    assert write_as in [
        "units",
        "processing",
    ], f"Argument write_as ({write_as}) should be one of 'units' or 'processing'!"
    if write_as == "units":
        assert units_name == "units", "When writing to the nwbfile.units table, the name of the table must be 'units'!"
    write_in_processing_module = False if write_as == "units" else True

    # retrieve templates and stds
    template_extension = sorting_analyzer.get_extension("templates")
    if template_extension is None:
        raise ValueError("No templates found in the sorting analyzer.")
    template_means = template_extension.get_templates()
    template_stds = template_extension.get_templates(operator="std")
    sorting = sorting_analyzer.sorting
    if unit_ids is not None:
        unit_indices = sorting.ids_to_indices(unit_ids)
        template_means = template_means[unit_indices]
        template_stds = template_stds[unit_indices]

    # metrics properties (quality, template) are added as properties to the sorting copy
    sorting_copy = sorting.select_units(unit_ids=sorting.unit_ids)
    if sorting_analyzer.has_extension("quality_metrics"):
        qm = sorting_analyzer.get_extension("quality_metrics").get_data()
        for prop in qm.columns:
            if prop not in sorting_copy.get_property_keys():
                sorting_copy.set_property(prop, qm[prop])
    if sorting_analyzer.has_extension("template_metrics"):
        tm = sorting_analyzer.get_extension("template_metrics").get_data()
        for prop in tm.columns:
            if prop not in sorting_copy.get_property_keys():
                sorting_copy.set_property(prop, tm[prop])

    # if recording is given, it takes precedence over the recording in the sorting analyzer
    if recording is None:
        assert sorting_analyzer.has_recording(), (
            "recording not found. To add the electrode table, the sorting_analyzer "
            "needs to have a recording attached or the 'recording' argument needs to be used."
        )
        recording = sorting_analyzer.recording

    add_recording_metadata_to_nwbfile(recording, nwbfile=nwbfile, metadata=metadata)
    electrode_group_indices = _get_electrode_group_indices(recording, nwbfile=nwbfile)
    unit_electrode_indices = [electrode_group_indices] * len(sorting.unit_ids)

    _add_units_table_to_nwbfile(
        sorting=sorting_copy,
        nwbfile=nwbfile,
        unit_ids=unit_ids,
        property_descriptions=property_descriptions,
        skip_properties=skip_properties,
        write_in_processing_module=write_in_processing_module,
        units_table_name=units_name,
        unit_table_description=units_description,
        waveform_means=template_means,
        waveform_sds=template_stds,
        unit_electrode_indices=unit_electrode_indices,
    )


def write_sorting_analyzer_to_nwbfile(
    sorting_analyzer: SortingAnalyzer,
    nwbfile_path: FilePath | None = None,
    nwbfile: pynwb.NWBFile | None = None,
    metadata: dict | None = None,
    overwrite: bool = False,
    recording: BaseRecording | None = None,
    verbose: bool = False,
    unit_ids: list[str] | list[int] | None = None,
    write_electrical_series: bool = False,
    add_electrical_series_kwargs: dict | None = None,
    skip_properties: list[str] | None = None,
    property_descriptions: dict | None = None,
    write_as: Literal["units", "processing"] = "units",
    units_name: str = "units",
    units_description: str = "Autogenerated by neuroconv.",
):
    """
    Convenience function to write directly a sorting analyzer object to an nwbfile.

    The function adds the data of the recording and the sorting plus the following information from the sorting analyzer:
    - quality metrics
    - template mean and std
    - template metrics

    Parameters
    ----------
    sorting_analyzer : spikeinterface.SortingAnalyzer
        The sorting analyzer object to be written to the NWBFile.
    nwbfile_path : FilePath
        Path for where to write or load (if overwrite=False) the NWBFile.
        If specified, the context will always write to this location.
    nwbfile : NWBFile, optional
        If passed, this function will fill the relevant fields within the NWBFile object.
        E.g., calling::

            write_recording(recording=my_recording_extractor, nwbfile=my_nwbfile)

        will result in the appropriate changes to the my_nwbfile object.
        If neither 'nwbfile_path' nor 'nwbfile' are specified, an NWBFile object will be automatically generated
        and returned by the function.
    metadata : dict, optional
        Metadata dictionary with information used to create the NWBFile when one does not exist or overwrite=True.
        The "Ecephys" section of metadata is also used to create electrodes and electrical series fields.
    overwrite : bool, default: False
        Whether to overwrite the NWBFile if one exists at the nwbfile_path.
    recording : BaseRecording, optional
        If the sorting_analyzer is 'recordingless', this argument is required to be passed to save electrode info.
    verbose : bool, default: False
        If 'nwbfile_path' is specified, informs user after a successful write operation.
    unit_ids : list, optional
        Controls the unit_ids that will be written to the nwb file. If None (default), all
        units are written.
    write_electrical_series : bool, default: False
        If True, the recording object associated to the analyzer is written as an electrical series.
    add_electrical_series_kwargs: dict, optional
        Keyword arguments to control the `add_electrical_series()` function in case write_electrical_series=True
    property_descriptions: dict, optional
        For each key in this dictionary which matches the name of a unit
        property in sorting, adds the value as a description to that
        custom unit column.
    skip_properties: list of str, optional
        Each string in this list that matches a unit property will not be written to the NWBFile.
    write_as: {'units', 'processing'}
        How to save the units table in the nwb file. Options:
        - 'units' will save it to the official NWBFile.Units position; recommended only for the final form of the data.
        - 'processing' will save it to the processing module to serve as a historical provenance for the official table.
    units_name : str, default: 'units'
        The name of the units table. If write_as=='units', then units_name must also be 'units'.
    units_description : str, default: 'Autogenerated by neuroconv.'
    """
    metadata = metadata if metadata is not None else dict()

    # if recording is given, it takes precedence over the recording in the sorting analyzer
    if recording is None and sorting_analyzer.has_recording():
        recording = sorting_analyzer.recording
    assert recording is not None, (
        "recording not found. To add the electrode table, the sorting_analyzer "
        "needs to have a recording attached or the 'recording' argument needs to be used."
    )

    # try:
    with make_or_load_nwbfile(
        nwbfile_path=nwbfile_path, nwbfile=nwbfile, metadata=metadata, overwrite=overwrite, verbose=verbose
    ) as nwbfile_out:

        if write_electrical_series:
            add_electrical_series_kwargs = add_electrical_series_kwargs or dict()
            add_recording_to_nwbfile(
                recording=recording, nwbfile=nwbfile_out, metadata=metadata, **add_electrical_series_kwargs
            )

        add_sorting_analyzer_to_nwbfile(
            sorting_analyzer=sorting_analyzer,
            nwbfile=nwbfile_out,
            metadata=metadata,
            recording=recording,
            unit_ids=unit_ids,
            skip_properties=skip_properties,
            property_descriptions=property_descriptions,
            write_as=write_as,
            units_name=units_name,
            units_description=units_description,
        )


def _get_electrode_group_indices(recording, nwbfile):
    """ """
    if "group_name" in recording.get_property_keys():
        group_names = np.unique(recording.get_property("group_name"))
    elif "group" in recording.get_property_keys():
        group_names = np.unique(recording.get_property("group"))
    else:
        group_names = None

    if group_names is None:
        electrode_group_indices = None
    else:
        group_names = [str(group_name) for group_name in group_names]
        electrode_group_indices = nwbfile.electrodes.to_dataframe().query(f"group_name in {group_names}").index.values
    return electrode_group_indices


def _stub_recording(recording: BaseRecording, *, stub_samples: int = 100) -> BaseRecording:
    """
    Create a stub recording object for the NWBFile.

    Parameters
    ----------
    recording : BaseRecording
        The recording extractor object.
    stub_samples : int, default: 100
        The length of the stub recording in frames.
    """

    number_of_segments = recording.get_num_segments()
    recording_segments = [recording.select_segments([index]) for index in range(number_of_segments)]

    # We clip the stub_samples if they are more than the number of samples in the segment
    end_frame_list = [min(stub_samples, segment.get_num_samples()) for segment in recording_segments]
    recording_segments_stubbed = [
        segment.frame_slice(start_frame=0, end_frame=end_frame)
        for segment, end_frame in zip(recording_segments, end_frame_list)
    ]
    recording_stubbed = AppendSegmentRecording(recording_list=recording_segments_stubbed)

    return recording_stubbed
