from copy import deepcopy
from typing import Literal

from pynwb import NWBFile

from neuroconv.tools import get_package


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
        if existing_value != value:
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
    """Add an optical physiology device instance to an NWBFile object."""
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


def add_optical_fibers(*, nwbfile: NWBFile, optical_fibers_metadata: list[dict]) -> None:
    """Add ``OpticalFiber`` devices to an NWBFile, idempotently by name.

    Optical fibers are a special case among devices: each carries a nested ``fiber_insertion``
    block and a ``model`` reference resolved from ``nwbfile.device_models``.
    """
    ndx_ophys_devices = get_package("ndx_ophys_devices")
    for optical_fiber_metadata in optical_fibers_metadata:
        name = optical_fiber_metadata["name"]
        if name in nwbfile.devices:
            _assert_metadata_matches_existing(nwbfile.devices[name], optical_fiber_metadata, name)
            continue

        optical_fiber_metadata = deepcopy(optical_fiber_metadata)
        optical_fiber_metadata["fiber_insertion"] = ndx_ophys_devices.FiberInsertion(
            **optical_fiber_metadata["fiber_insertion"]
        )
        model_name = optical_fiber_metadata["model"]
        assert (
            model_name in nwbfile.device_models
        ), f"Device model {model_name} not found in NWBFile device_models for {name}."
        optical_fiber_metadata["model"] = nwbfile.device_models[model_name]
        nwbfile.add_device(ndx_ophys_devices.OpticalFiber(**optical_fiber_metadata))


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


def add_fiber_photometry_lab_metadata(*, nwbfile: NWBFile, fiber_photometry_metadata: dict):
    """Build the shared ``FiberPhotometry`` lab metadata (viruses, injections, indicators, table).

    This is a build-once operation guarded by the presence of the ``"fiber_photometry"`` lab
    metadata: the first interface to run assembles the entire container from the (converter-merged)
    metadata, and subsequent interfaces reuse it. Any ``CommandedVoltageSeries`` referenced by a
    table row must already be present in ``nwbfile.acquisition``.

    Returns the ``FiberPhotometryTable`` so callers can build table regions.
    """
    ndx_fiber_photometry = get_package("ndx_fiber_photometry")
    ndx_ophys_devices = get_package("ndx_ophys_devices")

    if "fiber_photometry" in nwbfile.lab_meta_data:
        return nwbfile.lab_meta_data["fiber_photometry"].fiber_photometry_table

    name_to_viral_vector = {}
    for viral_vector_metadata in fiber_photometry_metadata.get("FiberPhotometryViruses", []):
        viral_vector = ndx_ophys_devices.ViralVector(**viral_vector_metadata)
        name_to_viral_vector[viral_vector.name] = viral_vector
    viruses = (
        ndx_fiber_photometry.FiberPhotometryViruses(viral_vectors=list(name_to_viral_vector.values()))
        if name_to_viral_vector
        else None
    )

    name_to_injection = {}
    for injection_metadata in fiber_photometry_metadata.get("FiberPhotometryVirusInjections", []):
        injection_metadata = deepcopy(injection_metadata)
        injection_metadata["viral_vector"] = name_to_viral_vector[injection_metadata["viral_vector"]]
        injection = ndx_ophys_devices.ViralVectorInjection(**injection_metadata)
        name_to_injection[injection.name] = injection
    virus_injections = (
        ndx_fiber_photometry.FiberPhotometryVirusInjections(viral_vector_injections=list(name_to_injection.values()))
        if name_to_injection
        else None
    )

    name_to_indicator = {}
    for indicator_metadata in fiber_photometry_metadata.get("FiberPhotometryIndicators", []):
        if "viral_vector_injection" in indicator_metadata:
            indicator_metadata = deepcopy(indicator_metadata)
            indicator_metadata["viral_vector_injection"] = name_to_injection[
                indicator_metadata["viral_vector_injection"]
            ]
        indicator = ndx_ophys_devices.Indicator(**indicator_metadata)
        name_to_indicator[indicator.name] = indicator
    if not name_to_indicator:
        raise ValueError("At least one indicator must be specified in the metadata.")
    indicators = ndx_fiber_photometry.FiberPhotometryIndicators(indicators=list(name_to_indicator.values()))

    table_metadata = fiber_photometry_metadata["FiberPhotometryTable"]
    fiber_photometry_table = ndx_fiber_photometry.FiberPhotometryTable(
        name=table_metadata["name"],
        description=table_metadata["description"],
    )
    device_fields = [
        "optical_fiber",
        "excitation_source",
        "photodetector",
        "dichroic_mirror",
        "excitation_filter",
        "emission_filter",
    ]
    for row_metadata in table_metadata["rows"]:
        row_data = {field: nwbfile.devices[row_metadata[field]] for field in device_fields if field in row_metadata}
        row_data["location"] = row_metadata["location"]
        row_data["excitation_wavelength_in_nm"] = row_metadata["excitation_wavelength_in_nm"]
        row_data["emission_wavelength_in_nm"] = row_metadata["emission_wavelength_in_nm"]
        row_data["indicator"] = name_to_indicator[row_metadata["indicator"]]
        if "coordinates" in row_metadata:
            row_data["coordinates"] = row_metadata["coordinates"]
        if "commanded_voltage_series" in row_metadata:
            row_data["commanded_voltage_series"] = nwbfile.acquisition[row_metadata["commanded_voltage_series"]]
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
    *, fiber_photometry_table, table_rows_metadata: list[dict], row_names: list[str], description: str
):
    """Resolve a list of table-row *names* to a ``FiberPhotometryTableRegion``.

    Row indices are derived from the position of each named row in the (converter-merged)
    ``table_rows_metadata`` — the same order the rows were added in — so regions never depend on
    fragile hand-written integer indices. Raises loudly if a referenced row name is not present.
    """
    name_to_index = {row["name"]: index for index, row in enumerate(table_rows_metadata)}
    missing = [name for name in row_names if name not in name_to_index]
    if missing:
        raise ValueError(
            f"FiberPhotometryResponseSeries references table row(s) {missing} that are not present "
            f"in the FiberPhotometryTable metadata (available: {list(name_to_index)})."
        )
    region = [name_to_index[name] for name in row_names]
    return fiber_photometry_table.create_fiber_photometry_table_region(description=description, region=region)
