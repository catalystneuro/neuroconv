from pynwb import NWBFile

from ..utils import DeepDict

# The key under which the default (placeholder) entries are registered. An interface re-keys these to its own
# file-derived keys; mirrors the ophys ``default_metadata_key``.
DEFAULT_METADATA_KEY = "default_metadata_key"


def _get_icephys_metadata_placeholders() -> DeepDict:
    """
    Default intracellular-electrophysiology metadata, keyed by a single ``default_metadata_key``.

    Mirrors the ophys placeholder pattern (`_get_ophys_metadata_placeholders`): the icephys metadata shape is
    defined once here so it is not re-spelled at each call site, and only the fields the NWB schema strictly
    requires carry a placeholder value, so as little metadata as possible is made up. An interface's
    ``get_metadata`` seeds its entries from these defaults and overrides the data-derived fields (the amplifier
    model, the channel-derived names, the file-derived keys); a field it leaves untouched falls back to the
    default here, and a future schema-required field added here propagates to every interface automatically.
    Each call returns an independent copy.

    Structure
    ---------
    - ``Devices[key]``: the amplifier. ``name`` only (``Device.description`` is optional, so none is invented).
    - ``Icephys.IntracellularElectrodes[key]``: the patch electrode, linked to its device by
      ``device_metadata_key``. ``description`` is schema-required, so it carries a ``"no description"``
      placeholder.
    - ``Icephys.PatchClampSeries[key]``: the response series, linked to its electrode by
      ``electrode_metadata_key``.
    """
    metadata = DeepDict()
    metadata["Devices"] = {
        DEFAULT_METADATA_KEY: {
            "name": "Amplifier",
        }
    }
    metadata["Icephys"] = {
        "IntracellularElectrodes": {
            DEFAULT_METADATA_KEY: {
                "name": "IntracellularElectrode",
                "description": "no description",
                "device_metadata_key": DEFAULT_METADATA_KEY,
            }
        },
        "PatchClampSeries": {
            DEFAULT_METADATA_KEY: {
                "name": "PatchClampSeries",
                "electrode_metadata_key": DEFAULT_METADATA_KEY,
            }
        },
    }
    return metadata


def _add_intracellular_electrode_to_nwbfile(nwbfile: NWBFile, metadata: dict, electrode_metadata_key: str):
    """Return the intracellular electrode named by the metadata entry ``electrode_metadata_key``, reusing an
    existing one by name or creating it (and its device) if absent.

    Resolves the electrode entry, follows its ``device_metadata_key`` link to the device entry, and fills any
    schema-required field the entry omits from :func:`_get_icephys_metadata_placeholders` (defaults are applied
    here, at write time, so an interface's ``get_metadata`` only returns what the source provides). The electrode
    and its device dedup by ``name``, so several interfaces pointing at the same name share one object.
    """
    placeholders = _get_icephys_metadata_placeholders()
    electrode_metadata = {
        **placeholders["Icephys"]["IntracellularElectrodes"][DEFAULT_METADATA_KEY],
        **metadata["Icephys"]["IntracellularElectrodes"][electrode_metadata_key],
    }
    device_metadata_key = electrode_metadata["device_metadata_key"]
    device_metadata = {
        **placeholders["Devices"][DEFAULT_METADATA_KEY],
        **metadata["Devices"][device_metadata_key],
    }

    name = electrode_metadata["name"]
    if name in nwbfile.icephys_electrodes:
        return nwbfile.icephys_electrodes[name]

    device_name = device_metadata["name"]
    if device_name in nwbfile.devices:
        device = nwbfile.devices[device_name]
    else:
        device = nwbfile.create_device(name=device_name, description=device_metadata.get("description"))
    # Optional IntracellularElectrode fields passed through from metadata if present.
    electrode_fields = ("cell_id", "location", "slice", "resistance", "seal", "filtering", "initial_access_resistance")
    extra_fields = {field: electrode_metadata[field] for field in electrode_fields if field in electrode_metadata}
    return nwbfile.create_icephys_electrode(
        name=name,
        description=electrode_metadata["description"],
        device=device,
        **extra_fields,
    )
