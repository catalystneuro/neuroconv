"""Tests for the shipped reference catalogue of fiber photometry hardware specifications.

These live here rather than in ``tests/test_minimal`` because the catalogue's central guarantee is
that every shipped row constructs as its real ``ndx-ophys-devices`` class, which needs the extension
installed. Constructing the class is what a JSON schema would otherwise have to describe: it catches
a missing required field, a misspelled key and a wrong dtype in one assertion, and it checks the rows
against the extension version this repository pins rather than against one recorded elsewhere.
"""

import pytest
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.fiber_photometry_hardware_catalogue import (
    _load_reference_device_models,
    get_reference_band_optical_filter_model,
    get_reference_excitation_source_model,
    get_reference_optical_fiber_model,
    get_reference_photodetector_model,
    list_reference_device_models,
)
from neuroconv.tools.nwb_helpers import _add_device_model_to_nwbfile

ndx_ophys_devices = pytest.importorskip("ndx_ophys_devices")


@pytest.mark.parametrize("entry", list_reference_device_models(), ids=lambda entry: entry["part"])
def test_every_reference_entry_constructs(entry):
    """Every shipped row must build its declared ndx-ophys-devices class."""
    model_metadata = dict(entry["model"])
    model_class = getattr(ndx_ophys_devices, model_metadata.pop("type"))

    model = model_class(name="test_model", **model_metadata)

    assert model.manufacturer == entry["model"]["manufacturer"]


def test_reference_parts_are_unique_within_a_manufacturer_and_type():
    """A part is addressed by type, manufacturer and part, so that triple is what must not repeat."""
    addresses = [
        (entry["model"]["type"], entry["model"]["manufacturer"], entry["part"])
        for entry in list_reference_device_models()
    ]

    assert len(addresses) == len(set(addresses))


def test_every_reference_entry_carries_a_specification():
    """A row whose only content is a manufacturer would construct fine and tell a user nothing.

    The class check cannot catch this, because most specification fields are optional: a
    ``DichroicMirrorModel`` needs nothing but a name and a manufacturer. So the rule that the
    catalogue ships published numbers rather than the fact that a vendor makes the part is a rule
    only a test can hold.
    """
    identity = {"type", "manufacturer", "model_number", "description"}
    for entry in list_reference_device_models():
        assert set(entry["model"]) - identity, entry["part"]


def test_a_dichroic_edge_sits_between_its_bands():
    """A dichroic's edge is where it stops reflecting and starts transmitting, so it lies between them.

    This is a property of the part rather than a convention, which makes it the one check that can
    catch a mistyped wavelength: a transposed digit moves the edge out from between the two bands
    while leaving a row that still constructs.
    """
    for entry in list_reference_device_models(model_type="DichroicMirrorModel"):
        model = entry["model"]
        if "reflection_band_in_nm" not in model or "transmission_band_in_nm" not in model:
            continue
        edge = model.get("cut_on_wavelength_in_nm", model.get("cut_off_wavelength_in_nm"))
        reflection, transmission = model["reflection_band_in_nm"], model["transmission_band_in_nm"]
        lower, upper = sorted((reflection, transmission), key=lambda band: band[0])

        assert lower[1] <= edge <= upper[0], entry["part"]


def test_every_reference_entry_is_traceable():
    """A specification without the page it was read from cannot be checked against its source."""
    for entry in list_reference_device_models():
        assert entry["source_url"].startswith("http"), entry["part"]
        # ``notes`` qualifies a value that needs qualifying, so a self-explanatory row leaves it empty.
        assert isinstance(entry["notes"], str), entry["part"]


def test_a_part_is_named_by_its_model_number_when_one_is_published():
    """A part the vendor numbers is looked up by that number, so the two must agree."""
    for entry in list_reference_device_models():
        model_number = entry["model"].get("model_number")
        if model_number is not None:
            assert entry["part"] == model_number


def test_parts_without_a_representable_model_state_why():
    """The gap list is what the docs page shows instead of a row, so it has to explain itself."""
    for part in _load_reference_device_models()["not_representable"]:
        assert part["reason"]
        assert part["published"]
        assert part["source_url"].startswith("http")


def test_listing_filters_by_manufacturer_and_type():
    fibers = list_reference_device_models(model_type="OpticalFiberModel")
    thorlabs = list_reference_device_models(manufacturer="thorlabs")

    assert {entry["model"]["type"] for entry in fibers} == {"OpticalFiberModel"}
    assert {entry["model"]["manufacturer"] for entry in thorlabs} == {"Thorlabs"}


def test_listed_entries_are_copies():
    """Callers edit what they get back, and the catalogue is cached, so it must not be shared."""
    list_reference_device_models()[0]["model"]["manufacturer"] = "edited"

    assert list_reference_device_models()[0]["model"]["manufacturer"] != "edited"


def test_get_returns_a_registry_entry():
    entry = get_reference_optical_fiber_model(manufacturer="Thorlabs", part="CFMC12L20")

    assert entry == dict(
        name="OpticalFiberModel",
        type="OpticalFiberModel",
        manufacturer="Thorlabs",
        model_number="CFMC12L20",
        numerical_aperture=0.39,
        core_diameter_in_um=200.0,
        ferrule_diameter_in_mm=2.5,
    )


def test_get_accepts_a_part_with_no_model_number():
    """Neurophotometrics publishes no per-part number, so those parts are named rather than numbered."""
    entry = get_reference_excitation_source_model(manufacturer="Neurophotometrics", part="FP3002 470 nm")

    assert entry["wavelength_range_in_nm"] == [445.0, 486.0]
    assert "model_number" not in entry


def test_get_names_the_model_after_its_class_by_default():
    doric = dict(manufacturer="Doric Lenses", part="CLED_470")

    assert get_reference_excitation_source_model(**doric)["name"] == "ExcitationSourceModel"
    assert get_reference_excitation_source_model(**doric, name="signal_source")["name"] == "signal_source"


def test_get_matches_case_insensitively():
    """A manufacturer is a company name and a part number is often shouted, so neither is exact."""
    entry = get_reference_optical_fiber_model(manufacturer="thorlabs", part="cfmc12l20")

    assert entry["model_number"] == "CFMC12L20"


def test_get_returns_copies():
    thorlabs = dict(manufacturer="Thorlabs", part="CFMC12L20")
    get_reference_optical_fiber_model(**thorlabs)["numerical_aperture"] = 0.99

    assert get_reference_optical_fiber_model(**thorlabs)["numerical_aperture"] == 0.39


def test_get_raises_on_an_unknown_manufacturer_and_lists_the_ones_it_holds():
    with pytest.raises(KeyError, match="Thorlabs"):
        get_reference_optical_fiber_model(manufacturer="Nonesuch Optics", part="CFMC12L20")


def test_get_raises_on_an_unknown_part_and_lists_that_manufacturer_s_parts():
    with pytest.raises(KeyError, match="CFMC12L20"):
        get_reference_optical_fiber_model(manufacturer="Thorlabs", part="CFMC12")


def test_get_will_not_find_a_part_under_the_wrong_model_type():
    """The model type is part of the address too: one product commonly yields several models."""
    with pytest.raises(KeyError, match="OpticalFiberModel"):
        get_reference_optical_fiber_model(manufacturer="Doric Lenses", part="FMC4 emission 500-550 nm")


def test_get_reaches_every_model_type():
    filter_model = get_reference_band_optical_filter_model(manufacturer="Doric Lenses", part="FMC4 emission 500-550 nm")
    detector = get_reference_photodetector_model(manufacturer="Newport", part="2151")

    assert filter_model["center_wavelength_in_nm"] == 525.0
    assert detector["gain_unit"] == "V/W"


def test_get_will_not_find_a_part_under_the_wrong_manufacturer():
    """The manufacturer is part of the address, not a hint, so it has to bind."""
    with pytest.raises(KeyError, match="Thorlabs"):
        get_reference_optical_fiber_model(manufacturer="Thorlabs", part="PS1")


def test_a_reference_entry_writes():
    """The write path passes an entry straight to the class, so a stray catalogue key would raise here."""
    entry = get_reference_optical_fiber_model(manufacturer="Thorlabs", part="CFMC12L20", name="OpticalFiber1")
    metadata = dict(DeviceModels={"optical_fiber_model": entry})
    nwbfile = mock_NWBFile()

    _add_device_model_to_nwbfile(nwbfile, metadata=metadata, metadata_key="optical_fiber_model")

    written = nwbfile.device_models["OpticalFiber1"]
    assert type(written) is ndx_ophys_devices.OpticalFiberModel
    assert written.numerical_aperture == 0.39
    assert written.model_number == "CFMC12L20"
