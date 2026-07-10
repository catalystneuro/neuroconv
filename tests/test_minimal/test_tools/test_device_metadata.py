"""Tests for the top-level ``DeviceModels`` / ``Devices`` metadata registry helpers.

These use only the core ``pynwb.device.Device`` / ``DeviceModel`` classes, so they run without any NWB
extension installed. The lazy extension-resolution path (``type`` naming an ndx subclass) is exercised
in ``tests/test_modalities/test_fiber_photometry`` where ``ndx-ophys-devices`` is available.
"""

import pytest
from pynwb.device import Device, DeviceModel
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.nwb_helpers import (
    _add_device_model_to_nwbfile,
    _add_device_to_nwbfile,
)
from neuroconv.tools.nwb_helpers._device_registry import (
    _DEVICE_MODEL_TYPE_SOURCES,
    _DEVICE_TYPE_SOURCES,
    _resolve_type,
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
        with pytest.raises(ValueError, match="not present in metadata\\['DeviceModels'\\]"):
            _add_device_model_to_nwbfile(nwbfile=nwbfile, metadata={"DeviceModels": {}}, metadata_key="absent")


class TestAddDeviceCanonical:
    def test_default_type_is_plain_device(self):
        nwbfile = mock_NWBFile()
        metadata = {"Devices": {"d": {"name": "d1", "description": "a probe"}}}
        device = _add_device_to_nwbfile(nwbfile=nwbfile, metadata=metadata, metadata_key="d")
        assert type(device) is Device
        assert nwbfile.devices["d1"].description == "a probe"

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
