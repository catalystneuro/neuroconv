from copy import deepcopy

import pytest

from neuroconv.tools.nwb_helpers._metadata_and_file_helpers import _validate_metadata_key, _validate_metadata_path
from neuroconv.utils import DeepDict


@pytest.fixture(params=[dict, DeepDict], ids=["dict", "DeepDict"])
def dictionary_type(request):
    return request.param


@pytest.mark.parametrize(
    "missing_level, expected",
    [
        (
            "Ophys",
            "metadata_key 'selected' was not found in metadata['Ophys']['MicroscopySeries'] "
            "because metadata has no 'Ophys' (available keys: ['NWBFile']).",
        ),
        (
            "MicroscopySeries",
            "metadata_key 'selected' was not found in metadata['Ophys']['MicroscopySeries'] "
            "because metadata['Ophys'] has no 'MicroscopySeries' (available keys: ['ImagingPlanes']).",
        ),
        (
            "selected",
            "metadata_key 'selected' was not found in metadata['Ophys']['MicroscopySeries'] "
            "(available keys: ['known']).",
        ),
    ],
)
def test_key_errors_name_the_first_missing_level_without_mutation(dictionary_type, missing_level, expected):
    registry = dictionary_type(known={}, selected={})
    ophys = dictionary_type(ImagingPlanes={}, MicroscopySeries=registry)
    metadata = dictionary_type(NWBFile={}, Ophys=ophys)
    parent = {
        "Ophys": metadata,
        "MicroscopySeries": metadata["Ophys"],
        "selected": metadata["Ophys"]["MicroscopySeries"],
    }[missing_level]
    del parent[missing_level]
    original = deepcopy(metadata)

    with pytest.raises(ValueError) as error:
        _validate_metadata_key(
            metadata, metadata_path=("Ophys", "MicroscopySeries"), metadata_key="selected", field="metadata_key"
        )

    assert str(error.value) == expected
    assert metadata == original


@pytest.mark.parametrize(
    "missing_level, expected",
    [
        (
            "FiberPhotometry",
            "Required metadata path metadata['FiberPhotometry']['FiberPhotometryTable']['rows'] is missing: "
            "metadata has no 'FiberPhotometry' (available keys: ['NWBFile']).",
        ),
        (
            "FiberPhotometryTable",
            "Required metadata path metadata['FiberPhotometry']['FiberPhotometryTable']['rows'] is missing: "
            "metadata['FiberPhotometry'] has no 'FiberPhotometryTable' (available keys: ['response']).",
        ),
        (
            "rows",
            "Required metadata path metadata['FiberPhotometry']['FiberPhotometryTable']['rows'] is missing: "
            "metadata['FiberPhotometry']['FiberPhotometryTable'] has no 'rows' (available keys: ['name']).",
        ),
    ],
)
def test_path_errors_name_the_first_missing_level_without_mutation(dictionary_type, missing_level, expected):
    table = dictionary_type(name="table", rows={})
    photometry = dictionary_type(response={}, FiberPhotometryTable=table)
    metadata = dictionary_type(NWBFile={}, FiberPhotometry=photometry)
    parent = {
        "FiberPhotometry": metadata,
        "FiberPhotometryTable": metadata["FiberPhotometry"],
        "rows": metadata["FiberPhotometry"]["FiberPhotometryTable"],
    }[missing_level]
    del parent[missing_level]
    original = deepcopy(metadata)

    with pytest.raises(ValueError) as error:
        _validate_metadata_path(metadata, ("FiberPhotometry", "FiberPhotometryTable", "rows"))

    assert str(error.value) == expected
    assert metadata == original


@pytest.mark.parametrize("entry", [{}, {"name": None}, None, "not a dictionary"])
def test_validators_only_check_existence(dictionary_type, entry):
    metadata = dictionary_type(Devices=dictionary_type(selected=entry))
    original = deepcopy(metadata)

    assert (
        _validate_metadata_key(
            metadata, metadata_path=("Devices",), metadata_key="selected", field="device_metadata_key"
        )
        is None
    )
    assert _validate_metadata_path(metadata, ("Devices", "selected")) is None
    assert metadata == original


def test_key_error_preserves_the_reference_field():
    with pytest.raises(ValueError) as error:
        _validate_metadata_key(
            {"Devices": {"camera": {}}},
            metadata_path=("Devices",),
            metadata_key="camera_typo",
            field="device_metadata_key",
        )

    assert str(error.value) == (
        "device_metadata_key 'camera_typo' was not found in metadata['Devices'] (available keys: ['camera'])."
    )
