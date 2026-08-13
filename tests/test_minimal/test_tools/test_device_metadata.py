"""Tests for the top-level ``DeviceModels`` / ``Devices`` metadata registry helpers.

These use only the core ``pynwb.device.Device`` / ``DeviceModel`` classes, so they run without any NWB
extension installed. The lazy extension-resolution path (``type`` naming an ndx subclass) is exercised
in ``tests/test_modalities/test_fiber_photometry`` where ``ndx-ophys-devices`` is available.
"""

import re
from datetime import datetime

import pytest
from pynwb.device import Device, DeviceModel
from pynwb.ophys import ImagingPlane, OpticalChannel
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.nwb_helpers import (
    _add_device_model_to_nwbfile,
    _add_device_to_nwbfile,
)
from neuroconv.tools.nwb_helpers._device_types import (
    _DEVICE_MODEL_TYPE_SOURCES,
    _DEVICE_TYPE_SOURCES,
    _build_inline_containers,
    _get_inline_container_class,
    _resolve_type,
)
from neuroconv.tools.testing.mock_interfaces import MockBehaviorEventInterface
from neuroconv.utils import DeepDict
from neuroconv.utils.json_schema import (
    _validate_device_registry_names,
    validate_metadata,
)


class TestResolveType:
    def test_base_class_returned_directly(self):
        assert _resolve_type("Device", sources=_DEVICE_TYPE_SOURCES, base_class=Device) is Device
        assert _resolve_type("DeviceModel", sources=_DEVICE_MODEL_TYPE_SOURCES, base_class=DeviceModel) is DeviceModel

    def test_unknown_type_raises_listing_known(self):
        with pytest.raises(ValueError, match="Unknown device type 'NotAType'"):
            _resolve_type("NotAType", sources=_DEVICE_TYPE_SOURCES, base_class=Device)
        with pytest.raises(ValueError, match="Known types"):
            _resolve_type("NotAModel", sources=_DEVICE_MODEL_TYPE_SOURCES, base_class=DeviceModel)


class TestAddDeviceModel:
    def test_default_type_is_plain_device_model(self):
        nwbfile = mock_NWBFile()
        metadata = {"DeviceModels": {"m": {"name": "model_1", "manufacturer": "ACME"}}}
        model = _add_device_model_to_nwbfile(nwbfile=nwbfile, metadata=metadata, metadata_key="m")
        assert type(model) is DeviceModel
        assert "model_1" in nwbfile.device_models
        assert model.manufacturer == "ACME"

    def test_idempotent_on_name(self):
        nwbfile = mock_NWBFile()
        metadata = {"DeviceModels": {"m": {"name": "model_1", "manufacturer": "ACME"}}}
        first = _add_device_model_to_nwbfile(nwbfile=nwbfile, metadata=metadata, metadata_key="m")
        second = _add_device_model_to_nwbfile(nwbfile=nwbfile, metadata=metadata, metadata_key="m")
        assert first is second
        assert len(nwbfile.device_models) == 1

    def test_missing_key_raises(self):
        nwbfile = mock_NWBFile()
        metadata = {"DeviceModels": {"a_model": {"name": "Model", "manufacturer": "ACME"}}}
        expected_message = (
            "device_model_metadata_key 'absent' was not found in metadata['DeviceModels'] "
            "(available keys: ['a_model'])."
        )
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            _add_device_model_to_nwbfile(nwbfile=nwbfile, metadata=metadata, metadata_key="absent")


class TestAddDeviceMissingKey:
    """A ``device_metadata_key`` naming nothing names the key, the registry and what is in it.

    Checked rather than indexed because the metadata reaching this helper is usually a ``DeepDict``,
    where a missing key auto-vivifies instead of raising and the failure surfaces several frames later
    as ``TypeError: unhashable type: 'DeepDict'``."""

    @pytest.mark.parametrize("registry", [dict(), DeepDict()], ids=["plain_dict", "deep_dict"])
    def test_missing_key_raises_the_curated_message(self, registry):
        nwbfile = mock_NWBFile()
        registry["a_camera"] = {"name": "Camera"}
        metadata = {"Devices": registry}
        expected_message = (
            "device_metadata_key 'a_camrea' was not found in metadata['Devices'] " "(available keys: ['a_camera'])."
        )
        with pytest.raises(ValueError, match=re.escape(expected_message)):
            _add_device_to_nwbfile(nwbfile=nwbfile, metadata=metadata, metadata_key="a_camrea")


@pytest.mark.parametrize(
    ("registry_name", "add_entry"),
    [
        ("Devices", _add_device_to_nwbfile),
        ("DeviceModels", _add_device_model_to_nwbfile),
    ],
)
@pytest.mark.parametrize(
    "second_entry",
    [{"name": "shared"}, {"name": "shared", "manufacturer": "Other"}],
    ids=["identical", "different"],
)
def test_duplicate_registry_names_raise(registry_name, add_entry, second_entry):
    metadata = {registry_name: {"a": {"name": "shared"}, "b": second_entry}}
    nwbfile = mock_NWBFile()

    with pytest.raises(ValueError, match="keys 'a' and 'b' use name 'shared'"):
        add_entry(nwbfile=nwbfile, metadata=metadata, metadata_key="a")

    container = nwbfile.devices if registry_name == "Devices" else nwbfile.device_models
    assert len(container) == 0


class TestAddDeviceCanonical:
    def test_default_type_is_plain_device(self):
        nwbfile = mock_NWBFile()
        metadata = {"Devices": {"d": {"name": "d1", "description": "a probe"}}}
        device = _add_device_to_nwbfile(nwbfile=nwbfile, metadata=metadata, metadata_key="d")
        assert type(device) is Device
        assert nwbfile.devices["d1"].description == "a probe"

    def test_idempotent_on_metadata_key(self):
        nwbfile = mock_NWBFile()
        metadata = {"Devices": {"d": {"name": "d1"}}}
        first = _add_device_to_nwbfile(nwbfile=nwbfile, metadata=metadata, metadata_key="d")
        second = _add_device_to_nwbfile(nwbfile=nwbfile, metadata=metadata, metadata_key="d")
        assert first is second
        assert len(nwbfile.devices) == 1

    def test_pulls_and_links_model_on_demand(self):
        nwbfile = mock_NWBFile()
        metadata = {
            "DeviceModels": {"m": {"name": "model_1", "manufacturer": "ACME"}},
            "Devices": {"d": {"name": "d1", "device_model_metadata_key": "m"}},
        }
        device = _add_device_to_nwbfile(nwbfile=nwbfile, metadata=metadata, metadata_key="d")
        assert "model_1" in nwbfile.device_models  # pulled on demand, no separate model pass
        assert device.model is nwbfile.device_models["model_1"]

    def test_requires_an_entry_source(self):
        nwbfile = mock_NWBFile()
        with pytest.raises(ValueError, match="Provide either"):
            _add_device_to_nwbfile(nwbfile=nwbfile)


class TestDuplicateRegistryNames:
    """A device or device model ``name`` must be claimed by exactly one metadata key."""

    @pytest.mark.parametrize("registry_name", ["Devices", "DeviceModels"])
    @pytest.mark.parametrize(
        "second_entry",
        [{"name": "shared"}, {"name": "shared", "description": "a different description"}],
        ids=["identical_entries", "conflicting_entries"],
    )
    def test_two_keys_one_name_raises(self, registry_name, second_entry):
        """Identical entries raise as loudly as conflicting ones: declaring twice is the mistake."""
        metadata = {registry_name: {"first": {"name": "shared"}, "second": second_entry}}

        with pytest.raises(ValueError, match="keys 'first' and 'second' use name 'shared'"):
            _validate_device_registry_names(metadata=metadata)

    def test_distinct_names_pass(self):
        metadata = {
            "Devices": {"a": {"name": "DeviceA"}, "b": {"name": "DeviceB"}},
            "DeviceModels": {"a": {"name": "ModelA"}, "b": {"name": "ModelB"}},
        }

        _validate_device_registry_names(metadata=metadata)

    def test_same_name_across_the_two_registries_passes(self):
        """``Devices`` and ``DeviceModels`` are separate namespaces in the NWB file."""
        metadata = {"Devices": {"a": {"name": "shared"}}, "DeviceModels": {"a": {"name": "shared"}}}

        _validate_device_registry_names(metadata=metadata)

    @pytest.mark.parametrize(
        "metadata",
        [{}, {"Devices": {}}, {"Devices": None}, {"Devices": {"a": None}}, {"Devices": {"a": {}}}],
        ids=["no_registry", "empty", "not_a_dict", "entry_not_a_dict", "entry_without_name"],
    )
    def test_incomplete_metadata_is_left_to_the_schema(self, metadata):
        """Shape errors belong to JSON schema validation, so this check skips rather than raises."""
        _validate_device_registry_names(metadata=metadata)

    def test_raises_before_anything_is_written(self):
        """The failure must arrive before a partially populated file exists."""
        nwbfile = mock_NWBFile()
        metadata = {"Devices": {"first": {"name": "shared"}, "second": {"name": "shared"}}}

        with pytest.raises(ValueError, match="use name 'shared'"):
            validate_metadata(metadata=metadata, schema={})

        assert len(nwbfile.devices) == 0

    def test_reported_through_an_interface(self):
        """The check reaches users through the ordinary interface validation entry point."""
        interface = MockBehaviorEventInterface()
        metadata = interface.get_metadata()
        metadata["NWBFile"]["session_start_time"] = datetime(2020, 1, 1, 12, 0, 0)
        metadata["Devices"] = {"first": {"name": "shared"}, "second": {"name": "shared"}}

        with pytest.raises(ValueError, match="use name 'shared'"):
            interface.validate_metadata(metadata=metadata)


class TestInlineContainerBuilder:
    """Sub-objects written inline as metadata dicts become the container the constructor declares."""

    def test_list_valued_argument_is_built(self):
        kwargs = {
            "name": "ImagingPlane",
            "optical_channel": [{"name": "channel", "description": "a channel", "emission_lambda": 500.0}],
        }

        built = _build_inline_containers(target_class=ImagingPlane, kwargs=kwargs)

        assert all(isinstance(channel, OpticalChannel) for channel in built["optical_channel"])
        assert built["optical_channel"][0].emission_lambda == 500.0

    def test_link_valued_argument_is_left_alone(self):
        """``ImagingPlane.device`` declares a ``Device``, but a device is linked, never inlined."""
        device = Device(name="Microscope")

        built = _build_inline_containers(target_class=ImagingPlane, kwargs={"device": device})

        assert built["device"] is device

    def test_plain_arguments_are_untouched(self):
        kwargs = {"name": "ImagingPlane", "excitation_lambda": 600.0, "location": "unknown"}

        assert _build_inline_containers(target_class=ImagingPlane, kwargs=dict(kwargs)) == kwargs

    def test_link_type_is_not_reported_as_inline(self):
        assert _get_inline_container_class(Device) == (None, False)

    def test_list_accepting_container_type_is_reported(self):
        container_class, accepts_list = _get_inline_container_class((list, OpticalChannel))

        assert container_class is OpticalChannel
        assert accepts_list is True

    def test_string_named_type_is_skipped(self):
        """hdmf allows a type named by string; those are links (``OpticalFiber.model``) here."""
        assert _get_inline_container_class("DeviceModel") == (None, False)

    def test_non_container_type_is_skipped(self):
        assert _get_inline_container_class(str) == (None, False)
