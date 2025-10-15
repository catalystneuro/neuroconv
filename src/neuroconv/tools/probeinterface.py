from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Literal

import numpy as np
import pynwb
from probeinterface import Probe, ProbeGroup
from pynwb.device import Device, DeviceModel

from ..datainterfaces.ecephys.spikeglx.spikeglx_utils import get_device_metadata

__all__ = (
    "add_probe_to_nwbfile",
    "add_spikeglx_probe_to_nwbfile",
    "populate_probe_contacts_in_nwbfile",
)


def _base_group_name(current_probe: Probe, probe_index: int) -> str:
    for candidate in (
        current_probe.name,
        current_probe.model_name,
        current_probe.annotations.get("probe_type") if hasattr(current_probe, "annotations") else None,
    ):
        if candidate:
            return str(candidate).replace(" ", "_")
    manufacturer = current_probe.manufacturer or "Probe"
    return f"{manufacturer}_{probe_index}"


def _prepare_contact_array(probegroup: ProbeGroup) -> np.ndarray:
    contact_array = probegroup.to_numpy(complete=True)
    dtype_names = contact_array.dtype.names

    if "device_channel_indices" in dtype_names:
        connected_mask = contact_array["device_channel_indices"] >= 0
        contact_array = contact_array[connected_mask]

    if contact_array.size == 0:
        raise ValueError("Probe does not contain any connected contacts.")

    if "device_channel_indices" in dtype_names:
        order = np.lexsort((contact_array["device_channel_indices"], contact_array["probe_index"]))
    else:
        order = np.lexsort((np.arange(contact_array.size), contact_array["probe_index"]))

    return contact_array[order]


def _ensure_contact_ids(contact_array: np.ndarray) -> np.ndarray:
    if "contact_ids" in contact_array.dtype.names:
        contact_ids = np.asarray(contact_array["contact_ids"]).astype("U")
    else:
        contact_ids = np.empty(contact_array.size, dtype="U")
        contact_ids[:] = ""

    missing_mask = contact_ids == ""
    if np.any(missing_mask):
        probe_indices = contact_array["probe_index"].astype(int)
        counters: dict[int, int] = {}
        for idx in np.where(missing_mask)[0]:
            probe_index = probe_indices[idx]
            count = counters.get(probe_index, 0)
            contact_ids[idx] = f"p{probe_index}c{count}"
            counters[probe_index] = count + 1

    if np.unique(contact_ids).size != contact_ids.size:
        raise ValueError(
            "Probe contains duplicate contact identifiers. Ensure each contact has a unique id before writing to NWB."
        )

    return contact_ids


def populate_probe_contacts_in_nwbfile(
    *,
    probegroup: ProbeGroup,
    contact_array: np.ndarray,
    group_names: np.ndarray,
    nwbfile: pynwb.NWBFile,
    metadata: dict | None = None,
) -> np.ndarray:
    """
    Populate electrodes, electrode groups, and device metadata in the NWB file using ProbeInterface data.

    Parameters
    ----------
    probegroup : ProbeGroup
        ProbeGroup describing the probe(s).
    contact_array : numpy.ndarray
        Structured array describing contacts, typically obtained from ``probegroup.to_numpy(complete=True)``
        or the recording ``contact_vector`` property.
    group_names : numpy.ndarray
        String array mapping each contact to its electrode group name.
    nwbfile : NWBFile
        Target NWBFile.
    metadata : dict | None
        Optional metadata used to fetch per-group descriptions and locations.

    Returns
    -------
    numpy.ndarray
        The contact identifiers used for ``electrode_name`` and ``contact_ids`` columns.
    """

    if contact_array.size != group_names.size:
        raise ValueError("The length of group_names must match the number of contacts.")

    contact_ids = _ensure_contact_ids(contact_array)

    ecephys_metadata = (metadata or {}).get("Ecephys", {})
    metadata_device_entries = ecephys_metadata.get("Device", [])
    metadata_group_entries = {
        entry.get("name"): entry
        for entry in ecephys_metadata.get("ElectrodeGroup", [])
        if isinstance(entry, dict) and "name" in entry
    }

    first_probe_index = int(contact_array["probe_index"][0])
    primary_probe = probegroup.probes[first_probe_index]
    serial_number = primary_probe.serial_number
    annotations = getattr(primary_probe, "annotations", {})
    manufacturer = primary_probe.manufacturer or annotations.get("manufacturer") or "unspecified manufacturer"
    model_number = annotations.get("part_number") or annotations.get("model_number")
    probe_type = annotations.get("probe_type")

    metadata_device_entry = None
    if metadata_device_entries:
        # Choose an entry matching our automatic device name if present, otherwise use the first provided entry.
        for entry in metadata_device_entries:
            if entry.get("name"):
                metadata_device_entry = entry
                break
        if metadata_device_entry is None:
            metadata_device_entry = metadata_device_entries[0]

    derived_device_name = _base_group_name(primary_probe, first_probe_index) + "Device"
    device_name = metadata_device_entry.get("name") if metadata_device_entry else derived_device_name
    device_description = metadata_device_entry.get("description") if metadata_device_entry else None
    if device_description is None:
        device_description = (
            f"Probe instance imported from probeinterface ({primary_probe.model_name or 'unknown model'})."
        )
        if serial_number:
            device_description += f" Serial number: {serial_number}."
    device_serial = metadata_device_entry.get("serial_number") if metadata_device_entry else serial_number

    device_model = None
    device_model_name = metadata_device_entry.get("model") if metadata_device_entry else primary_probe.model_name
    if device_model_name is None:
        device_model_name = _base_group_name(primary_probe, first_probe_index)
    device_model_description = metadata_device_entry.get("model_description") if metadata_device_entry else None
    if device_model_description is None and probe_type is not None:
        device_model_description = f"probe_type={probe_type}"

    if hasattr(nwbfile, "add_device_model") and hasattr(nwbfile, "device_models"):
        device_models_container = getattr(nwbfile, "device_models", None)
        existing_model = None
        if device_models_container is not None and hasattr(device_models_container, "get"):
            existing_model = device_models_container.get(device_model_name)
        if existing_model is not None:
            device_model = existing_model
        else:
            device_model_kwargs = dict(name=device_model_name, manufacturer=manufacturer)
            if model_number is not None:
                device_model_kwargs["model_number"] = str(model_number)
            if device_model_description:
                device_model_kwargs["description"] = device_model_description
            device_model = DeviceModel(**device_model_kwargs)
            nwbfile.add_device_model(device_model)

    if device_name in nwbfile.devices:
        device = nwbfile.devices[device_name]
        if device_model is not None and getattr(device, "model", None) is None:
            device.model = device_model
        if device_serial and getattr(device, "serial_number", None) in (None, ""):
            device.serial_number = str(device_serial)
        if device_description and not getattr(device, "description", None):
            device.description = device_description
    else:
        device_kwargs = dict(name=device_name, description=device_description)
        if device_serial:
            device_kwargs["serial_number"] = str(device_serial)
        if device_model is not None:
            device_kwargs["model"] = device_model
        device = Device(**device_kwargs)
        nwbfile.add_device(device)

    group_names = np.asarray(group_names).astype("U")
    metadata_group_lookup = {name: metadata_group_entries.get(name, {}) for name in set(group_names)}

    for group_name, group_metadata in metadata_group_lookup.items():
        if group_name in nwbfile.electrode_groups:
            continue
        description = group_metadata.get("description") or f"Electrode group derived from probe '{group_name}'."
        location = group_metadata.get("location") or group_metadata.get("brain_region") or "unknown"
        nwbfile.create_electrode_group(name=group_name, description=description, location=location, device=device)

    existing_lookup: dict[tuple[str, str], int] = {}
    if nwbfile.electrodes is not None and len(nwbfile.electrodes) > 0:
        has_electrode_name_column = "electrode_name" in nwbfile.electrodes.colnames
        for row_index in range(len(nwbfile.electrodes)):
            group_name = nwbfile.electrodes["group_name"][row_index]
            electrode_name = nwbfile.electrodes["electrode_name"][row_index] if has_electrode_name_column else ""
            existing_lookup[(group_name, electrode_name)] = row_index

    dtype_names = contact_array.dtype.names
    fields_to_skip = {"x", "y", "z", "probe_index", "device_channel_indices", "contact_ids"}

    for index, group_name in enumerate(group_names):
        contact_id = contact_ids[index]
        lookup_key = (group_name, contact_id)
        if lookup_key in existing_lookup:
            continue

        row_kwargs = dict(
            x=float(contact_array["x"][index]),
            y=float(contact_array["y"][index]),
            z=float(contact_array["z"][index]) if "z" in dtype_names else float("nan"),
            imp=np.nan,
            filtering="",
            location=nwbfile.electrode_groups[group_name].location or "unknown",
            group=nwbfile.electrode_groups[group_name],
            group_name=group_name,
            electrode_name=contact_id,
            contact_ids=contact_id,
            contact_shapes=contact_array["contact_shapes"][index],
        )

        if "si_units" in dtype_names:
            row_kwargs["si_units"] = contact_array["si_units"][index]
        if "shank_ids" in dtype_names:
            row_kwargs["shank_ids"] = contact_array["shank_ids"][index]

        for field in dtype_names:
            if field in fields_to_skip or field in ("contact_shapes", "si_units", "shank_ids"):
                continue
            value = contact_array[field][index]
            if isinstance(value, np.ndarray):
                row_kwargs[field] = value.tolist()
            else:
                row_kwargs[field] = value

        nwbfile.add_electrode(**row_kwargs, enforce_unique_id=True)
        existing_lookup[lookup_key] = len(nwbfile.electrodes) - 1

    return contact_ids


def add_probe_to_nwbfile(
    probe: Probe | ProbeGroup,
    nwbfile: pynwb.NWBFile,
    *,
    group_mode: Literal["by_probe", "by_shank"] = "by_probe",
    metadata: dict | None = None,
) -> None:
    """
    Populate the NWB electrodes table using only probe metadata.
    """
    if probe is None:
        raise ValueError("Missing probe definition. Provide a Probe or ProbeGroup instance.")

    if isinstance(probe, Probe):
        probegroup = ProbeGroup()
        probegroup.add_probe(probe)
    elif isinstance(probe, ProbeGroup):
        probegroup = probe
    else:
        raise TypeError("`probe` must be a probeinterface.Probe or ProbeGroup.")

    contact_array = _prepare_contact_array(probegroup)
    probe_indices = contact_array["probe_index"].astype(int)

    if group_mode == "by_probe":
        group_names = np.asarray(
            [_base_group_name(probegroup.probes[index], index) for index in probe_indices], dtype="U"
        )
    elif group_mode == "by_shank":
        if "shank_ids" not in contact_array.dtype.names:
            raise ValueError("group_mode='by_shank' requires shank_ids in the probe definition.")
        shank_ids = contact_array["shank_ids"].astype("U")
        group_names = []
        for probe_index, shank_id in zip(probe_indices, shank_ids):
            base = _base_group_name(probegroup.probes[probe_index], probe_index)
            suffix = f"Shank{shank_id}" if shank_id not in ("", None, "") else "Shank0"
            group_names.append(f"{base}{suffix}")
        group_names = np.asarray(group_names, dtype="U")
    else:
        raise ValueError("group_mode must be either 'by_probe' or 'by_shank'.")

    populate_probe_contacts_in_nwbfile(
        probegroup=probegroup,
        contact_array=contact_array,
        group_names=group_names,
        nwbfile=nwbfile,
        metadata=metadata,
    )


def add_spikeglx_probe_to_nwbfile(
    meta_file: str | Path,
    nwbfile: pynwb.NWBFile,
    *,
    group_mode: Literal["by_probe", "by_shank"] = "by_shank",
    metadata: dict | None = None,
) -> None:
    """
    Parse a SpikeGLX ``.meta`` file and add the corresponding Neuropixels probe to the NWB electrodes table.
    """
    from probeinterface.neuropixels_tools import parse_spikeglx_meta, read_spikeglx

    meta_path = Path(meta_file)
    spikeglx_meta = parse_spikeglx_meta(meta_path)
    spikeglx_probe = read_spikeglx(meta_path)

    effective_metadata = deepcopy(metadata) if metadata is not None else {}
    ecephys_metadata = effective_metadata.setdefault("Ecephys", {})
    device_entries = ecephys_metadata.setdefault("Device", [])
    spikeglx_device_metadata = get_device_metadata(spikeglx_meta)
    if not any(device.get("name") == spikeglx_device_metadata["name"] for device in device_entries):
        device_entries.append(spikeglx_device_metadata)

    add_probe_to_nwbfile(
        probe=spikeglx_probe,
        nwbfile=nwbfile,
        group_mode=group_mode,
        metadata=effective_metadata,
    )
