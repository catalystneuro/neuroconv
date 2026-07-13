from copy import deepcopy
from typing import Literal

from pynwb import NWBFile

from neuroconv.tools import get_package
from neuroconv.tools.nwb_helpers import (
    _add_device_model_to_nwbfile,
    _add_device_to_nwbfile,
)

#: Sentinel written into required string metadata fields the user has not filled in. It is a distinct
#: value from a deliberate ``"unknown"`` so an intentional "unknown" silences the placeholder warning.
FIBER_PHOTOMETRY_PLACEHOLDER = "PLACEHOLDER"

#: FiberPhotometryTable row reference fields (``<field>_metadata_key``) mapping to the ndx row column.
_ROW_DEVICE_KEY_FIELDS = {
    "optical_fiber_metadata_key": "optical_fiber",
    "excitation_source_metadata_key": "excitation_source",
    "photodetector_metadata_key": "photodetector",
    "dichroic_mirror_metadata_key": "dichroic_mirror",
    "excitation_filter_metadata_key": "excitation_filter",
    "emission_filter_metadata_key": "emission_filter",
}


def get_default_fiber_photometry_metadata(metadata_key: str) -> dict:
    """Return the default metadata scaffold for a single-series fiber photometry interface.

    Devices and device models live in the shared top-level ``metadata["Devices"]`` /
    ``metadata["DeviceModels"]`` registry (added in #1780): each entry carries a ``type`` naming its
    concrete class and a device links its model with ``device_model_metadata_key``. The remaining fiber
    photometry containers (indicators, the ``FiberPhotometryTable``, and this interface's response
    series) live under ``metadata["FiberPhotometry"]``, keyed by ``metadata_key`` and referencing each
    other — and the shared devices — with ``_metadata_key`` fields. Required fields are pre-filled with
    sentinels — ``NaN`` for the required numeric wavelengths and :data:`FIBER_PHOTOMETRY_PLACEHOLDER` for
    required strings — so an interface runs on zero user metadata while ``add_to_nwbfile`` warns about any
    surviving sentinel. ``metadata_key`` scopes this interface's response-series entry.
    """
    placeholder = FIBER_PHOTOMETRY_PLACEHOLDER
    device_models = {
        "optical_fiber_model": dict(
            type="OpticalFiberModel",
            name="optical_fiber_model",
            manufacturer=placeholder,
            numerical_aperture=float("nan"),
        ),
        "excitation_source_model": dict(
            type="ExcitationSourceModel",
            name="excitation_source_model",
            manufacturer=placeholder,
            source_type=placeholder,
            excitation_mode=placeholder,
        ),
        "photodetector_model": dict(
            type="PhotodetectorModel",
            name="photodetector_model",
            manufacturer=placeholder,
            detector_type=placeholder,
        ),
    }
    devices = {
        "optical_fiber": dict(
            type="OpticalFiber",
            name="optical_fiber",
            device_model_metadata_key="optical_fiber_model",
            fiber_insertion=dict(),
        ),
        "excitation_source": dict(
            type="ExcitationSource",
            name="excitation_source",
            device_model_metadata_key="excitation_source_model",
        ),
        "photodetector": dict(
            type="Photodetector",
            name="photodetector",
            device_model_metadata_key="photodetector_model",
        ),
    }
    fiber_photometry_metadata = dict(
        FiberPhotometryIndicators={"indicator": dict(name="indicator", label=placeholder)},
        FiberPhotometryTable=dict(
            name="fiber_photometry_table",
            description=placeholder,
            rows={
                "row0": dict(
                    location=placeholder,
                    excitation_wavelength_in_nm=float("nan"),
                    emission_wavelength_in_nm=float("nan"),
                    indicator_metadata_key="indicator",
                    optical_fiber_metadata_key="optical_fiber",
                    excitation_source_metadata_key="excitation_source",
                    photodetector_metadata_key="photodetector",
                )
            },
        ),
    )
    fiber_photometry_metadata[metadata_key] = dict(
        name="FiberPhotometryResponseSeries",
        description=placeholder,
        unit="a.u.",
        fiber_photometry_table_region=["row0"],
        fiber_photometry_table_region_description=placeholder,
    )
    return dict(DeviceModels=device_models, Devices=devices, FiberPhotometry=fiber_photometry_metadata)


def _assert_metadata_matches_existing(existing_object, metadata: dict, name: str) -> None:
    """Raise if scalar fields in ``metadata`` disagree with an already-added NWB object.

    Shared fiber photometry objects (devices, models, indicators, ...) are added once and reused
    across interfaces. When a second interface supplies metadata for a same-named object, the
    scalar fields must match exactly; otherwise a silent reuse would hide an authoring mistake.
    Only scalar fields present on both sides are compared — object-reference fields (e.g. ``model``)
    are skipped.
    """
    scalar_types = (str, int, float, bool)
    for key, value in metadata.items():
        if key == "name":
            continue
        existing_value = getattr(existing_object, key, None)
        if not isinstance(value, scalar_types) or not isinstance(existing_value, scalar_types):
            continue
        # A float is NaN iff it is not equal to itself; two NaN placeholders are not a real conflict.
        both_nan = value != value and existing_value != existing_value
        if existing_value != value and not both_nan:
            raise ValueError(
                f"Conflicting fiber photometry metadata for '{name}': field '{key}' is "
                f"{existing_value!r} on the already-added object but {value!r} in the new metadata. "
                "Shared objects must be identical across interfaces."
            )


def add_ophys_device_model(
    *,
    nwbfile: NWBFile,
    device_metadata: dict,
    device_type: Literal[
        "OpticalFiberModel",
        "ExcitationSourceModel",
        "PhotodetectorModel",
        "BandOpticalFilterModel",
        "EdgeOpticalFilterModel",
        "DichroicMirrorModel",
    ],
):
    """Add an optical physiology device model to an NWBFile object."""
    valid_device_types = [
        "OpticalFiberModel",
        "ExcitationSourceModel",
        "PhotodetectorModel",
        "BandOpticalFilterModel",
        "EdgeOpticalFilterModel",
        "DichroicMirrorModel",
    ]
    assert device_type in valid_device_types, f"device_type must be one of {valid_device_types}"
    ndx_ophys_devices = get_package("ndx_ophys_devices")

    device_name = device_metadata["name"]
    if device_name in nwbfile.device_models:
        _assert_metadata_matches_existing(nwbfile.device_models[device_name], device_metadata, device_name)
        return

    ophys_device_model = dict(
        OpticalFiberModel=ndx_ophys_devices.OpticalFiberModel,
        ExcitationSourceModel=ndx_ophys_devices.ExcitationSourceModel,
        PhotodetectorModel=ndx_ophys_devices.PhotodetectorModel,
        BandOpticalFilterModel=ndx_ophys_devices.BandOpticalFilterModel,
        EdgeOpticalFilterModel=ndx_ophys_devices.EdgeOpticalFilterModel,
        DichroicMirrorModel=ndx_ophys_devices.DichroicMirrorModel,
    )[device_type](**device_metadata)

    nwbfile.add_device_model(ophys_device_model)


def add_ophys_device(
    *,
    nwbfile: NWBFile,
    device_metadata: dict,
    device_type: Literal[
        "ExcitationSource",
        "Photodetector",
        "BandOpticalFilter",
        "EdgeOpticalFilter",
        "DichroicMirror",
    ],
):
    """Add an optical physiology device instance to an NWBFile object.

    ``device_metadata["model"]`` is the *name* of an already-added device model; the caller resolves any
    ``model_metadata_key`` reference to that name before calling this function.
    """
    valid_device_types = [
        "ExcitationSource",
        "Photodetector",
        "BandOpticalFilter",
        "EdgeOpticalFilter",
        "DichroicMirror",
    ]
    assert device_type in valid_device_types, f"device_type must be one of {valid_device_types}"
    ndx_ophys_devices = get_package("ndx_ophys_devices")

    device_name = device_metadata["name"]
    if device_name in nwbfile.devices:
        _assert_metadata_matches_existing(nwbfile.devices[device_name], device_metadata, device_name)
        return

    if isinstance(device_metadata["model"], str):
        assert (
            device_metadata["model"] in nwbfile.device_models
        ), f"Device model {device_metadata['model']} not found in NWBFile devices for {device_name}."
        device_model = nwbfile.device_models[device_metadata["model"]]
        device_metadata = deepcopy(device_metadata)
        device_metadata["model"] = device_model

    ophys_device = dict(
        OpticalFiber=ndx_ophys_devices.OpticalFiber,
        ExcitationSource=ndx_ophys_devices.ExcitationSource,
        Photodetector=ndx_ophys_devices.Photodetector,
        BandOpticalFilter=ndx_ophys_devices.BandOpticalFilter,
        EdgeOpticalFilter=ndx_ophys_devices.EdgeOpticalFilter,
        DichroicMirror=ndx_ophys_devices.DichroicMirror,
    )[device_type](**device_metadata)

    nwbfile.add_device(ophys_device)


def add_fiber_photometry_devices(*, nwbfile: NWBFile, metadata: dict) -> None:
    """Add all fiber photometry device models and instances to an NWBFile via the shared registry.

    Device models and instances live in the top-level ``metadata["DeviceModels"]`` /
    ``metadata["Devices"]`` registry (added in #1780) and are written with the shared
    :func:`~neuroconv.tools.nwb_helpers._add_device_model_to_nwbfile` /
    :func:`~neuroconv.tools.nwb_helpers._add_device_to_nwbfile` helpers, idempotently by name. Each
    device links its model with ``device_model_metadata_key``, resolved on demand by the canonical
    helper. Optical fibers are the one special case: each carries a nested ``fiber_insertion`` dict,
    built here into an ``ndx_ophys_devices.FiberInsertion`` and passed through the helper's pre-resolved
    (transitional) form.
    """
    for device_model_metadata_key in metadata.get("DeviceModels", {}):
        _add_device_model_to_nwbfile(nwbfile=nwbfile, metadata=metadata, metadata_key=device_model_metadata_key)

    for device_metadata_key, device_metadata in metadata.get("Devices", {}).items():
        if "fiber_insertion" not in device_metadata:
            _add_device_to_nwbfile(nwbfile=nwbfile, metadata=metadata, metadata_key=device_metadata_key)
            continue
        # Optical fiber: build the nested FiberInsertion and resolve the model, then use the helper's
        # transitional form (a pre-resolved entry dict) since the canonical form cannot build sub-objects.
        ndx_ophys_devices = get_package("ndx_ophys_devices")
        model = _add_device_model_to_nwbfile(
            nwbfile=nwbfile, metadata=metadata, metadata_key=device_metadata["device_model_metadata_key"]
        )
        resolved = {key: value for key, value in device_metadata.items() if key != "device_model_metadata_key"}
        resolved["fiber_insertion"] = ndx_ophys_devices.FiberInsertion(**device_metadata["fiber_insertion"])
        resolved["model"] = model
        _add_device_to_nwbfile(nwbfile=nwbfile, device_metadata=resolved)


def add_commanded_voltage_series(
    *,
    nwbfile: NWBFile,
    name: str,
    description: str,
    data,
    unit: str,
    frequency: float,
    timing_kwargs: dict,
):
    """Add a ``CommandedVoltageSeries`` to ``nwbfile.acquisition``, idempotently by name.

    Returns the (possibly pre-existing) series so a table row can reference it.
    """
    ndx_fiber_photometry = get_package("ndx_fiber_photometry")
    if name in nwbfile.acquisition:
        return nwbfile.acquisition[name]
    commanded_voltage_series = ndx_fiber_photometry.CommandedVoltageSeries(
        name=name,
        description=description,
        data=data,
        unit=unit,
        frequency=frequency,
        **timing_kwargs,
    )
    nwbfile.add_acquisition(commanded_voltage_series)
    return commanded_voltage_series


def add_fiber_photometry_lab_metadata(*, nwbfile: NWBFile, fiber_photometry_metadata: dict, devices_metadata: dict):
    """Build the shared ``FiberPhotometry`` lab metadata (viruses, injections, indicators, table).

    This is a build-once operation guarded by the presence of the ``"fiber_photometry"`` lab
    metadata: the first interface to run assembles the entire container from the (converter-merged)
    metadata, and subsequent interfaces reuse it. Devices and any ``CommandedVoltageSeries`` referenced
    by a table row must already be present in the NWBFile. Entries reference each other with
    ``_metadata_key`` fields (e.g. a table row's ``optical_fiber_metadata_key``), resolved here — device
    keys against the top-level ``devices_metadata`` (``metadata["Devices"]``).

    Returns the ``FiberPhotometryTable`` so callers can build table regions.
    """
    ndx_fiber_photometry = get_package("ndx_fiber_photometry")
    ndx_ophys_devices = get_package("ndx_ophys_devices")

    if "fiber_photometry" in nwbfile.lab_meta_data:
        return nwbfile.lab_meta_data["fiber_photometry"].fiber_photometry_table

    key_to_viral_vector = {}
    for viral_vector_metadata_key, viral_vector_metadata in fiber_photometry_metadata.get(
        "FiberPhotometryViruses", {}
    ).items():
        key_to_viral_vector[viral_vector_metadata_key] = ndx_ophys_devices.ViralVector(**viral_vector_metadata)
    viruses = (
        ndx_fiber_photometry.FiberPhotometryViruses(viral_vectors=list(key_to_viral_vector.values()))
        if key_to_viral_vector
        else None
    )

    key_to_injection = {}
    for injection_metadata_key, injection_metadata in fiber_photometry_metadata.get(
        "FiberPhotometryVirusInjections", {}
    ).items():
        viral_vector_metadata_key = injection_metadata["viral_vector_metadata_key"]
        injection_metadata = {
            key: value for key, value in injection_metadata.items() if key != "viral_vector_metadata_key"
        }
        injection_metadata["viral_vector"] = key_to_viral_vector[viral_vector_metadata_key]
        key_to_injection[injection_metadata_key] = ndx_ophys_devices.ViralVectorInjection(**injection_metadata)
    virus_injections = (
        ndx_fiber_photometry.FiberPhotometryVirusInjections(viral_vector_injections=list(key_to_injection.values()))
        if key_to_injection
        else None
    )

    key_to_indicator = {}
    for indicator_metadata_key, indicator_metadata in fiber_photometry_metadata.get(
        "FiberPhotometryIndicators", {}
    ).items():
        injection_key = indicator_metadata.get("viral_vector_injection_metadata_key")
        indicator_metadata = {
            key: value for key, value in indicator_metadata.items() if key != "viral_vector_injection_metadata_key"
        }
        if injection_key is not None:
            indicator_metadata["viral_vector_injection"] = key_to_injection[injection_key]
        key_to_indicator[indicator_metadata_key] = ndx_ophys_devices.Indicator(**indicator_metadata)
    if not key_to_indicator:
        raise ValueError("At least one indicator must be specified in the metadata.")
    indicators = ndx_fiber_photometry.FiberPhotometryIndicators(indicators=list(key_to_indicator.values()))

    # Maps to resolve a device/commanded-voltage _metadata_key to the NWB object's name.
    instance_key_to_name = {
        device_metadata_key: device_metadata["name"]
        for device_metadata_key, device_metadata in devices_metadata.items()
    }
    commanded_voltage_key_to_name = {
        key: value["name"] for key, value in fiber_photometry_metadata.get("CommandedVoltageSeries", {}).items()
    }

    table_metadata = fiber_photometry_metadata["FiberPhotometryTable"]
    fiber_photometry_table = ndx_fiber_photometry.FiberPhotometryTable(
        name=table_metadata["name"],
        description=table_metadata["description"],
    )
    for row_metadata in table_metadata["rows"].values():
        row_data = {}
        for key_field, ndx_field in _ROW_DEVICE_KEY_FIELDS.items():
            if key_field in row_metadata:
                row_data[ndx_field] = nwbfile.devices[instance_key_to_name[row_metadata[key_field]]]
        row_data["location"] = row_metadata["location"]
        row_data["excitation_wavelength_in_nm"] = row_metadata["excitation_wavelength_in_nm"]
        row_data["emission_wavelength_in_nm"] = row_metadata["emission_wavelength_in_nm"]
        row_data["indicator"] = key_to_indicator[row_metadata["indicator_metadata_key"]]
        if "coordinates" in row_metadata:
            row_data["coordinates"] = row_metadata["coordinates"]
        if "commanded_voltage_series_metadata_key" in row_metadata:
            commanded_voltage_name = commanded_voltage_key_to_name[
                row_metadata["commanded_voltage_series_metadata_key"]
            ]
            row_data["commanded_voltage_series"] = nwbfile.acquisition[commanded_voltage_name]
        fiber_photometry_table.add_row(**row_data)

    fiber_photometry_lab_metadata = ndx_fiber_photometry.FiberPhotometry(
        name="fiber_photometry",
        fiber_photometry_table=fiber_photometry_table,
        fiber_photometry_viruses=viruses,
        fiber_photometry_virus_injections=virus_injections,
        fiber_photometry_indicators=indicators,
    )
    nwbfile.add_lab_meta_data(fiber_photometry_lab_metadata)
    return fiber_photometry_table


def get_fiber_photometry_table_region(
    *, fiber_photometry_table, table_rows_metadata: dict, row_metadata_keys: list[str], description: str
):
    """Resolve a list of table-row *metadata keys* to a ``FiberPhotometryTableRegion``.

    Row indices are derived from the position of each keyed row in the (converter-merged)
    ``table_rows_metadata`` dict — the same order the rows were added in — so regions never depend on
    fragile hand-written integer indices. Raises loudly if a referenced row key is not present.
    """
    key_to_index = {row_metadata_key: index for index, row_metadata_key in enumerate(table_rows_metadata)}
    missing = [row_metadata_key for row_metadata_key in row_metadata_keys if row_metadata_key not in key_to_index]
    if missing:
        raise ValueError(
            f"FiberPhotometryResponseSeries references table row(s) {missing} that are not present "
            f"in the FiberPhotometryTable metadata (available: {list(key_to_index)})."
        )
    region = [key_to_index[row_metadata_key] for row_metadata_key in row_metadata_keys]
    return fiber_photometry_table.create_fiber_photometry_table_region(description=description, region=region)
