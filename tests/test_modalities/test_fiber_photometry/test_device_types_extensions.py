"""Extension-backed tests for the device registry: lazy resolution of ndx-ophys-devices classes.

These live here rather than in ``tests/test_minimal`` because they need ``ndx-ophys-devices``, which
is installed for the fiber photometry test job. The core, extension-free registry behavior is covered
in ``tests/test_minimal/test_tools/test_device_metadata.py``.
"""

import pytest
from pynwb.device import Device, DeviceModel
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.tools.nwb_helpers import _add_device_model_to_nwbfile
from neuroconv.tools.nwb_helpers._device_registry import (
    _DEVICE_MODEL_TYPE_SOURCES,
    _DEVICE_TYPE_SOURCES,
    _resolve_type,
)

ndx_ophys_devices = pytest.importorskip("ndx_ophys_devices")


def test_resolve_extension_model_type_lazily():
    resolved = _resolve_type("OpticalFiberModel", sources=_DEVICE_MODEL_TYPE_SOURCES, base_class=DeviceModel)
    assert resolved is ndx_ophys_devices.OpticalFiberModel


def test_resolve_extension_instance_type_lazily():
    resolved = _resolve_type("ExcitationSource", sources=_DEVICE_TYPE_SOURCES, base_class=Device)
    assert resolved is ndx_ophys_devices.ExcitationSource


def test_add_extension_device_model():
    nwbfile = mock_NWBFile()
    metadata = dict(
        DeviceModels={
            "m": dict(type="OpticalFiberModel", name="fiber_model", manufacturer="Doric", numerical_aperture=0.48)
        }
    )
    model = _add_device_model_to_nwbfile(nwbfile, metadata=metadata, metadata_key="m")
    assert type(model) is ndx_ophys_devices.OpticalFiberModel
    assert nwbfile.device_models["fiber_model"].numerical_aperture == 0.48
