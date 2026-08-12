"""Render ``fiber_photometry_device_models.rst`` from the shipped reference catalogue.

The page and the data that fills ``metadata["DeviceModels"]`` are the same rows, so writing the
tables by hand would only let the two disagree. Run this after editing the catalogue::

    python docs/user_guide/_generate_fiber_photometry_device_models.py

``tests/test_modalities/test_fiber_photometry/test_reference_device_models_docs.py`` fails if the
committed page is not what this produces.
"""

import json
from pathlib import Path

REPOSITORY_ROOT_PATH = Path(__file__).resolve().parent.parent.parent
REFERENCE_DATA_PATH = REPOSITORY_ROOT_PATH / "src" / "neuroconv" / "reference_data"
CATALOGUE_FILE_PATH = REFERENCE_DATA_PATH / "fiber_photometry_device_models.json"
PAGE_FILE_PATH = REPOSITORY_ROOT_PATH / "docs" / "user_guide" / "fiber_photometry_device_models.rst"


def format_gain(model: dict) -> str | None:
    """Render a photodetector's gain with its unit, since the figure means nothing without one."""
    present = [format_value(model[field]) for field in ("gain", "gain_unit") if field in model]
    return " ".join(present) if present else None


#: Per model type: the page section, its introduction, and the specification columns as (heading, field).
TABLE_SPECIFICATIONS = {
    "OpticalFiberModel": (
        "Optical fibers",
        "Doric parts are keyed by the ordering-code fragment that describes the fiber, the core and "
        "cladding diameters followed by the numerical aperture. The complete ordering code also encodes "
        "the ferrule type and the length, so check yours rather than assuming the fragment is the whole "
        "part number.",
        [
            ("Numerical aperture", "numerical_aperture"),
            ("Core diameter (um)", "core_diameter_in_um"),
            ("Ferrule diameter (mm)", "ferrule_diameter_in_mm"),
        ],
    ),
    "ExcitationSourceModel": (
        "Excitation sources",
        "Every source here is a one-photon light-emitting diode, so ``source_type`` and "
        "``excitation_mode`` are filled with those values and left out of the table. Tucker-Davis "
        "Technologies publishes only a nominal center wavelength for the Lux sources, with no bandwidth, "
        "so those rows carry the center in their description and no range at all. Neurophotometrics "
        "publishes no model number for the FP3002's onboard sources, so those parts are looked up by "
        "their product name instead.\n\n"
        "Doric renumbered its connectorized light-emitting diodes in a 2025 Generation-2 redesign, "
        "prefixing the codes with ``CLED_G2_`` and moving the blue channel from 465 to 470 nm. Both "
        "generations are listed, because a rig built before the change carries ``CLED_465`` and the "
        "bare code ``CLED_470`` has never been a Doric ordering code at all.",
        [
            ("Wavelength range (nm)", "wavelength_range_in_nm"),
        ],
    ),
    "BandOpticalFilterModel": (
        "Optical filters",
        "Doric's fluorescence mini-cubes carry the filters that set a rig's actual excitation and "
        "emission bands, and publish them as passbands. Every one is a bandpass filter, so "
        "``filter_type`` is filled with that and left out of the table, and the center and bandwidth "
        "below are the published passband restated in the fields the model provides, with the interval "
        "itself kept in each row's description. A mini-cube's bands are chosen when it is ordered, and "
        "its ordering code records the ones it was built with, so these rows describe the GCaMP "
        "configuration each product page documents rather than every cube of that model.\n\n"
        "The cubes' dichroic mirrors are not shipped. Doric describes them in prose, and publishes no "
        "cut-on wavelength, transmission band or angle of incidence for them on the product pages, in "
        "the mini-cube manuals or in the mechanical drawings. Inferring an edge from the surrounding "
        "passbands would be a guess, so there is nothing here to look up.",
        [
            ("Center wavelength (nm)", "center_wavelength_in_nm"),
            ("Bandwidth (nm)", "bandwidth_in_nm"),
        ],
    ),
    "DichroicMirrorModel": (
        "Dichroic mirrors",
        "The dichroic is what sets a rig's spectral geometry, splitting excitation from the returning "
        "fluorescence, and only the vendors who sell them as parts publish an edge. Doric is not among "
        "them: it describes the dichroics inside its mini-cubes but states no wavelength for any of "
        "them, so a stock Doric or Tucker-Davis rig cannot fill one of these rows from public "
        "information. Every value here is the vendor's published figure at the angle of incidence the "
        "vendor specifies, so a part mounted at a different angle has a different edge in practice.",
        [
            ("Cut-on (nm)", "cut_on_wavelength_in_nm"),
            ("Cut-off (nm)", "cut_off_wavelength_in_nm"),
            ("Reflection band (nm)", "reflection_band_in_nm"),
            ("Transmission band (nm)", "transmission_band_in_nm"),
        ],
    ),
    "EdgeOpticalFilterModel": (
        "Edge filters",
        "Longpass and shortpass filters, specified at normal incidence. Never read a cut wavelength "
        "off a part number: Semrock's ``BLP01-488R-25`` is named for the 488 nm laser line it serves "
        "and its published edge is 500 nm. None of these vendors publishes the slope figures the model "
        "also accepts, so those fields stay empty.",
        [
            ("Filter type", "filter_type"),
            ("Cut wavelength (nm)", "cut_wavelength_in_nm"),
        ],
    ),
    "PhotodetectorModel": (
        "Photodetectors",
        "A gain is shipped only where the vendor publishes a single figure for it, which rules out the "
        "two detectors whose gain is a setting rather than a specification.",
        [
            ("Detector type", "detector_type"),
            ("Wavelength range (nm)", "wavelength_range_in_nm"),
            ("Gain", format_gain),
        ],
    ),
}

PREAMBLE = """.. _fiber_photometry_device_models:

Fiber photometry hardware specification catalogue
=================================================

.. This page is generated from ``src/neuroconv/reference_data/fiber_photometry_device_models.json``
   by ``docs/user_guide/_generate_fiber_photometry_device_models.py``. Edit the catalogue, not this file.

No fiber photometry format records what hardware produced the recording. A Doric file names the
console, not the modules plugged into it; TDT, Neurophotometrics and comma-separated-value exports
carry no device specifications at all. The numerical aperture of a fiber, the wavelength range of an
excitation source and the gain of a photodetector are therefore not readable from the data, and
``get_metadata()`` will never supply them.

They are, however, published. The tables below collect the specifications the vendors state for
common fiber photometry hardware, each row carrying the page its values came from, so a device model
can be filled by finding the part rather than by inventing numbers.

Filling the metadata
--------------------

There is one function per model type. Look up your part by its manufacturer and part number, and put
what comes back into the metadata ``get_metadata()`` returned:

.. code-block:: python

    from neuroconv.tools.fiber_photometry_hardware_catalogue import get_reference_optical_fiber_model

    metadata = interface.get_metadata()
    metadata["DeviceModels"]["optical_fiber_model"] = get_reference_optical_fiber_model(
        manufacturer="Thorlabs", part="CFMC12L20"
    )

The others are ``get_reference_excitation_source_model``, ``get_reference_photodetector_model``,
``get_reference_band_optical_filter_model``, ``get_reference_edge_optical_filter_model`` and
``get_reference_dichroic_mirror_model``.

A part is addressed by all three of model type, manufacturer and part number, because neither of the
last two identifies it alone. A part number means something only relative to who issued it, and short
ones like ``2151`` or ``PS1`` are exactly the kind that collide. One product commonly yields several
models, too: a fluorescence mini-cube is filters and dichroic mirrors at once, and an FP3002 is
excitation sources and a detector, so the type is what separates ``FMC4 emission 500-550 nm`` from the
cube it sits in. Manufacturer and part are matched case-insensitively.

Parts whose vendor publishes no model number are addressed by their product name, and ``name`` sets
what the model is written as when the default, its class name, does not suit:

.. code-block:: python

    metadata["DeviceModels"]["excitation_source_model"] = get_reference_excitation_source_model(
        manufacturer="Neurophotometrics",
        part="FP3002 470 nm",
        name="isosbestic_source_model",
    )

What comes back is an ordinary dictionary, so edit it as you would any other metadata: a value you
read off your own hardware simply replaces the published one. ``list_reference_device_models()``
returns every part covered, filtered by manufacturer or by model type.

Before you use a row
--------------------

Check the part against the rig that produced the recording. Product lines change, so treat the source
link as the authority rather than the table. Per-lab customization is common, and fiber photometry
rigs mix vendors freely, so a Doric console frequently runs a Newport photoreceiver and Thorlabs
fibers. A vendor-branded row is not evidence about what a given laboratory physically had.

Photodetector gain is the weakest field throughout. It is a switchable setting on the Doric and
Newport detectors, printed without a unit by Tucker-Davis Technologies, and unpublished for the
Neurophotometrics camera, so leave it unset unless you read it off your own device configuration.
"""

CLOSING = """
Parts with no representable model
---------------------------------

These specifications are published, but they do not fit the fields the extension defines, so they are
not shipped as rows. Fill them by hand, deciding for yourself what to record.

"""


def format_value(value) -> str:
    """Render a catalogue value for a reStructuredText table cell."""
    if value is None:
        return "\\-"
    if isinstance(value, list):
        return " to ".join(format_value(element) for element in value)
    if isinstance(value, float):
        if value >= 1e6:
            return f"{value:.0e}".replace("e+", "e")
        if value == int(value):
            return str(int(value))
        return str(value)
    return str(value)


def render_table(entries: list[dict], specification_columns: list[tuple[str, str]]) -> str:
    """Render one model type's entries as a ``list-table``."""
    # Manufacturer leads because a part is addressed by that pair, in that order.
    headings = ["Manufacturer", "Part", *[heading for heading, _ in specification_columns], "Notes", "Source"]
    widths = [10, 14, *[7] * len(specification_columns), 45, 7]

    lines = [
        ".. list-table::",
        f"   :widths: {' '.join(str(width) for width in widths)}",
        "   :header-rows: 1",
        "",
    ]
    for index, heading in enumerate(headings):
        lines.append(f"   {'*' if index == 0 else ' '} - {heading}")
    for entry in entries:
        model = entry["model"]
        cells = [
            model["manufacturer"],
            f"``{entry['part']}``",
            *[
                format_value(field(model) if callable(field) else model.get(field))
                for _, field in specification_columns
            ],
            entry["notes"],
            f"`page <{entry['source_url']}>`__",
        ]
        for index, cell in enumerate(cells):
            # An empty cell would leave a trailing space, which the pre-commit hook strips back out.
            lines.append(f"   {'*' if index == 0 else ' '} - {cell}".rstrip())
    lines.append("")
    return "\n".join(lines)


def render_not_representable(parts: list[dict]) -> str:
    lines = []
    for part in parts:
        lines.append(f"**{part['part']}** ({part['manufacturer']}, {part['type']})")
        lines.append("")
        lines.append(f"   Published: {part['published']}. {part['reason']}")
        lines.append(f"   `Source <{part['source_url']}>`__")
        lines.append("")
    return "\n".join(lines)


def render_page() -> str:
    with open(CATALOGUE_FILE_PATH, "r", encoding="utf-8") as file:
        catalogue = json.load(file)

    sections = [PREAMBLE]
    for model_type, (title, introduction, specification_columns) in TABLE_SPECIFICATIONS.items():
        entries = [entry for entry in catalogue["device_models"] if entry["model"]["type"] == model_type]
        sections.append(f"\n{title}\n{'-' * len(title)}\n")
        sections.append(f"{introduction}\n")
        sections.append(render_table(entries=entries, specification_columns=specification_columns))
    sections.append(CLOSING)
    sections.append(render_not_representable(catalogue["not_representable"]))
    return "\n".join(sections)


if __name__ == "__main__":
    with open(PAGE_FILE_PATH, "w", encoding="utf-8") as file:
        file.write(render_page())
    print(f"Wrote {PAGE_FILE_PATH}")
