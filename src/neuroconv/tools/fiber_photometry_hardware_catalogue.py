"""Published specifications for commercial fiber photometry hardware, and the lookups over them.

This is curated vendor data rather than conversion code. Nothing else in NeuroConv asserts what a
piece of hardware *is*; every other module reports what a file says. That difference is why the
catalogue lives in a module of its own: it has no dependency on any interface, its only tie to the
rest of the library is the shape of a ``metadata["DeviceModels"]`` entry, and if it ever outgrows
NeuroConv it can be extracted as a package without unpicking anything.

The data itself is ``src/neuroconv/reference_data/fiber_photometry_device_models.json``, and the
user guide page is rendered from that same file so the table and the lookups cannot disagree.
"""

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

#: Published hardware specifications shipped with the package; see ``list_reference_device_models``.
_REFERENCE_DEVICE_MODELS_FILE_PATH = (
    Path(__file__).parent.parent / "reference_data" / "fiber_photometry_device_models.json"
)


@lru_cache(maxsize=1)
def _load_reference_device_models() -> dict:
    """Read the shipped catalogue once and cache it; callers get copies, never this dict."""
    with open(_REFERENCE_DEVICE_MODELS_FILE_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def list_reference_device_models(*, manufacturer: str | None = None, model_type: str | None = None) -> list[dict]:
    """Return the shipped hardware specifications, optionally filtered.

    No fiber photometry format records the fiber, excitation source or photodetector specifications,
    but the hardware is standard commercial equipment whose vendors publish them. This is that
    published data, read off datasheets and carrying the page each value came from, so a device model
    can be filled by finding the part rather than by inventing numbers.

    Each entry has a ``part`` naming it (its model number where the vendor publishes one, its product
    name otherwise), a ``source_url``, ``notes`` about how to read the row, and the ``model`` fields
    themselves. ``notes`` describes the catalogue row and is not written to the file; a ``description``
    inside ``model`` is a field of the NWB object and is written.

    Parameters
    ----------
    manufacturer : str, optional
        Keep only the parts made by this manufacturer, compared case-insensitively.
    model_type : str, optional
        Keep only this ndx-ophys-devices class, e.g. ``"OpticalFiberModel"``.

    Returns
    -------
    list of dict
        The matching entries, freshly copied so a caller may edit them.

    Notes
    -----
    Verify a row against your own hardware before writing it. Product lines change, per-lab
    customization is common, and a vendor-branded row may not be what a given rig physically has.
    """
    entries = deepcopy(_load_reference_device_models()["device_models"])
    if manufacturer is not None:
        entries = [entry for entry in entries if entry["model"]["manufacturer"].lower() == manufacturer.lower()]
    if model_type is not None:
        entries = [entry for entry in entries if entry["model"]["type"] == model_type]
    return entries


def _get_reference_model(*, model_type: str, manufacturer: str, part: str, name: str | None) -> dict:
    """Resolve one catalogue row to a ``metadata["DeviceModels"]`` entry.

    A part is addressed by its model type, its manufacturer and its part number, in narrowing order.
    Manufacturer belongs in the address because a part number means something only relative to who
    issued it, and model type belongs there because one product commonly yields several: a Doric
    fluorescence mini-cube is filters and dichroic mirrors at once, and a Neurophotometrics FP3002 is
    excitation sources and a detector. Manufacturer and part are matched case-insensitively.
    """
    entries = [entry for entry in list_reference_device_models() if entry["model"]["type"] == model_type]

    manufacturers = {entry["model"]["manufacturer"] for entry in entries}
    matched = {candidate for candidate in manufacturers if candidate.lower() == manufacturer.lower()}
    if not matched:
        raise KeyError(
            f"'{manufacturer}' makes no {model_type} in the fiber photometry reference catalogue, "
            f"which holds {model_type} parts from {sorted(manufacturers)}."
        )
    matched_manufacturer = matched.pop()

    parts = {
        entry["part"].lower(): entry for entry in entries if entry["model"]["manufacturer"] == matched_manufacturer
    }
    if part.lower() not in parts:
        raise KeyError(
            f"'{part}' is not a {matched_manufacturer} {model_type} in the fiber photometry reference "
            f"catalogue, which holds {sorted(entry['part'] for entry in parts.values())}. State the "
            "specifications yourself if your hardware is not one of them."
        )

    model = parts[part.lower()]["model"]
    return {"name": name if name is not None else model["type"], **model}


def get_reference_optical_fiber_model(*, manufacturer: str, part: str, name: str | None = None) -> dict:
    """Return an optical fiber's published specifications as a ``metadata["DeviceModels"]`` entry.

    The catalogue is a lookup for hardware the recording file does not describe, so this is called
    while editing the metadata ``get_metadata()`` returned, never from inside it: which fiber a rig
    used is knowledge the person who ran it supplies, not something to infer from the data. Check the
    part against your own hardware before writing it.

    Parameters
    ----------
    manufacturer : str
        The manufacturer, as the catalogue spells it, e.g. ``"Thorlabs"``.
    part : str
        The part: its model number where the vendor publishes one (``"CFMC12L20"``), its product name
        otherwise. ``list_reference_device_models(model_type="OpticalFiberModel")`` returns them all.
    name : str, optional
        The name the model is written under. Defaults to ``"OpticalFiberModel"``, which is what a file
        holding one of each carries; pass your own when a file holds two.

    Returns
    -------
    dict
        A ready registry entry: the ``type``, the ``name``, and the published specifications.

    Examples
    --------
    >>> from neuroconv.tools.fiber_photometry import get_reference_optical_fiber_model
    >>> get_reference_optical_fiber_model(manufacturer="Thorlabs", part="CFMC12L20")["numerical_aperture"]
    0.39
    """
    return _get_reference_model(model_type="OpticalFiberModel", manufacturer=manufacturer, part=part, name=name)


def get_reference_excitation_source_model(*, manufacturer: str, part: str, name: str | None = None) -> dict:
    """Return an excitation source's published specifications as a ``metadata["DeviceModels"]`` entry.

    See :func:`get_reference_optical_fiber_model` for how a part is addressed and why the catalogue is
    a lookup rather than something ``get_metadata()`` fills.

    Parameters
    ----------
    manufacturer : str
        The manufacturer, as the catalogue spells it, e.g. ``"Doric Lenses"``.
    part : str
        The part, e.g. ``"CLED_470"``. Neurophotometrics publishes no model number for the FP3002's
        onboard sources, so those are addressed by product name.
    name : str, optional
        The name the model is written under. Defaults to ``"ExcitationSourceModel"``.

    Returns
    -------
    dict
        A ready registry entry: the ``type``, the ``name``, and the published specifications.
    """
    return _get_reference_model(model_type="ExcitationSourceModel", manufacturer=manufacturer, part=part, name=name)


def get_reference_photodetector_model(*, manufacturer: str, part: str, name: str | None = None) -> dict:
    """Return a photodetector's published specifications as a ``metadata["DeviceModels"]`` entry.

    See :func:`get_reference_optical_fiber_model` for how a part is addressed and why the catalogue is
    a lookup rather than something ``get_metadata()`` fills. Gain is the weakest field here: it is a
    switchable setting on some detectors and printed without a unit on others, so read it off your own
    device configuration rather than trusting a default.

    Parameters
    ----------
    manufacturer : str
        The manufacturer, as the catalogue spells it, e.g. ``"Newport"``.
    part : str
        The part, e.g. ``"2151"``.
    name : str, optional
        The name the model is written under. Defaults to ``"PhotodetectorModel"``.

    Returns
    -------
    dict
        A ready registry entry: the ``type``, the ``name``, and the published specifications.
    """
    return _get_reference_model(model_type="PhotodetectorModel", manufacturer=manufacturer, part=part, name=name)


def get_reference_band_optical_filter_model(*, manufacturer: str, part: str, name: str | None = None) -> dict:
    """Return a bandpass filter's published specifications as a ``metadata["DeviceModels"]`` entry.

    See :func:`get_reference_optical_fiber_model` for how a part is addressed and why the catalogue is
    a lookup rather than something ``get_metadata()`` fills.

    Parameters
    ----------
    manufacturer : str
        The manufacturer, as the catalogue spells it, e.g. ``"Doric Lenses"``.
    part : str
        The part, e.g. ``"FMC4 emission 500-550 nm"``. A fluorescence mini-cube holds several filters,
        so a part names the one you mean rather than the cube.
    name : str, optional
        The name the model is written under. Defaults to ``"BandOpticalFilterModel"``.

    Returns
    -------
    dict
        A ready registry entry: the ``type``, the ``name``, and the published specifications.
    """
    return _get_reference_model(model_type="BandOpticalFilterModel", manufacturer=manufacturer, part=part, name=name)


def get_reference_edge_optical_filter_model(*, manufacturer: str, part: str, name: str | None = None) -> dict:
    """Return an edge filter's published specifications as a ``metadata["DeviceModels"]`` entry.

    See :func:`get_reference_optical_fiber_model` for how a part is addressed and why the catalogue is
    a lookup rather than something ``get_metadata()`` fills. A cut wavelength is the vendor's published
    figure at the angle of incidence the vendor specifies, which for these parts is normal incidence;
    mounting one at an angle moves its edge, and the catalogue cannot know how you mounted yours.

    Parameters
    ----------
    manufacturer : str
        The manufacturer, as the catalogue spells it, e.g. ``"Thorlabs"``.
    part : str
        The part, e.g. ``"FELH0500"``. Do not read a cut wavelength off a part number: Semrock's
        ``BLP01-488R-25`` is named for the laser line it serves and its published edge is 500 nm.
    name : str, optional
        The name the model is written under. Defaults to ``"EdgeOpticalFilterModel"``.

    Returns
    -------
    dict
        A ready registry entry: the ``type``, the ``name``, and the published specifications.
    """
    return _get_reference_model(model_type="EdgeOpticalFilterModel", manufacturer=manufacturer, part=part, name=name)


def get_reference_dichroic_mirror_model(*, manufacturer: str, part: str, name: str | None = None) -> dict:
    """Return a dichroic mirror's published specifications as a ``metadata["DeviceModels"]`` entry.

    See :func:`get_reference_optical_fiber_model` for how a part is addressed and why the catalogue is
    a lookup rather than something ``get_metadata()`` fills. These are the parts that define a rig's
    spectral geometry, and they are only catalogued for the vendors that publish an edge: Doric
    describes the dichroics inside its fluorescence mini-cubes but states no wavelength for them.

    Parameters
    ----------
    manufacturer : str
        The manufacturer, as the catalogue spells it, e.g. ``"Semrock"``.
    part : str
        The part, e.g. ``"FF495-Di04-25x36"``.
    name : str, optional
        The name the model is written under. Defaults to ``"DichroicMirrorModel"``.

    Returns
    -------
    dict
        A ready registry entry: the ``type``, the ``name``, and the published specifications.
    """
    return _get_reference_model(model_type="DichroicMirrorModel", manufacturer=manufacturer, part=part, name=name)
