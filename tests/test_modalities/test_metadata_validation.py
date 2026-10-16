from copy import deepcopy
from functools import partial

import pytest
from pynwb.testing.mock.file import mock_NWBFile

from neuroconv.datainterfaces.icephys.baseicephysinterface import BaseIcephysInterface
from neuroconv.tools.icephys import _add_intracellular_electrode_to_nwbfile, _add_patch_clamp_series_to_nwbfile
from neuroconv.tools.spikeinterface import add_recording_as_time_series_to_nwbfile, add_recording_to_nwbfile
from neuroconv.tools.testing.mock_interfaces import (
    MockEventsInterface,
    MockFiberPhotometryInterface,
    MockImagingInterface,
    MockPoseEstimationInterface,
    MockRecordingInterface,
    MockSegmentationInterface,
)
from neuroconv.utils import DeepDict


@pytest.mark.parametrize("dictionary_type", [dict, DeepDict], ids=["dict", "DeepDict"])
@pytest.mark.parametrize("missing", ["section", "registry", "entry"])
@pytest.mark.parametrize(
    "interface_factory, registry_path",
    [
        (MockImagingInterface, ("Ophys", "MicroscopySeries")),
        (MockSegmentationInterface, ("Ophys", "PlaneSegmentations")),
        (partial(MockRecordingInterface, durations=(0.01,)), ("Ecephys", "ElectricalSeries")),
        (MockPoseEstimationInterface, ("Pose", "PoseEstimations")),
        (MockFiberPhotometryInterface, ("FiberPhotometry",)),
        (MockEventsInterface, ("Events",)),
    ],
    ids=["imaging", "segmentation", "recording", "pose", "fiber_photometry", "events"],
)
def test_writers_reject_missing_metadata_without_mutation(interface_factory, registry_path, missing, dictionary_type):
    interface = interface_factory(metadata_key="selected")
    metadata = dictionary_type(NWBFile={})
    location = "metadata" + "".join(f"[{level!r}]" for level in registry_path)
    expected = f"metadata_key 'selected' was not found in {location}"
    if missing == "section" or (missing == "registry" and len(registry_path) == 1):
        expected += f" because metadata has no '{registry_path[0]}' (available keys: ['NWBFile'])."
    elif missing == "registry":
        metadata[registry_path[0]] = dictionary_type(other={})
        expected += f" because metadata['{registry_path[0]}'] has no '{registry_path[1]}' (available keys: ['other'])."
    else:
        parent = metadata
        for level in registry_path:
            parent[level] = dictionary_type()
            parent = parent[level]
        parent["known"] = {}
        expected += " (available keys: ['known'])."
    original = deepcopy(metadata)

    with pytest.raises(ValueError) as error:
        if isinstance(interface, MockRecordingInterface):
            add_recording_to_nwbfile(
                recording=interface.recording_extractor,
                nwbfile=mock_NWBFile(),
                metadata=metadata,
                metadata_key="selected",
            )
        else:
            interface.add_to_nwbfile(nwbfile=mock_NWBFile(), metadata=metadata)

    assert str(error.value) == expected
    assert metadata == original


def test_explicit_time_series_key_requires_its_registry():
    interface = MockRecordingInterface(durations=(0.01,))
    metadata = DeepDict(NWBFile={})
    original = deepcopy(metadata)

    with pytest.raises(ValueError) as error:
        add_recording_as_time_series_to_nwbfile(
            recording=interface.recording_extractor, nwbfile=mock_NWBFile(), metadata=metadata, metadata_key="selected"
        )

    assert str(error.value) == (
        "metadata_key 'selected' was not found in metadata['TimeSeries'] "
        "because metadata has no 'TimeSeries' (available keys: ['NWBFile'])."
    )
    assert metadata == original


def test_events_requires_event_types_but_not_table_overrides():
    interface = MockEventsInterface(metadata_key="selected")
    metadata = DeepDict(Events=DeepDict(selected=DeepDict()))
    original = deepcopy(metadata)

    with pytest.raises(ValueError) as error:
        interface.add_to_nwbfile(nwbfile=mock_NWBFile(), metadata=metadata)

    assert str(error.value) == (
        "Required metadata path metadata['Events']['selected']['event_types'] is missing: "
        "metadata['Events']['selected'] has no 'event_types' (available keys: [])."
    )
    assert metadata == original

    metadata = interface.get_metadata()
    metadata["Events"].pop("EventTables", None)
    nwbfile = mock_NWBFile()
    interface.add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
    assert nwbfile.events


class _IcephysInterface(BaseIcephysInterface):
    _series_metadata_key = "selected"

    def _get_icephys_series_data(self):
        raise AssertionError("Missing response metadata must be caught before reading the data.")


@pytest.mark.parametrize("registry", ["PatchClampSeries", "PatchClampStimulusSeries", "IntracellularElectrodes"])
def test_intracellular_references_require_registered_entries(registry):
    metadata = DeepDict(Icephys=DeepDict({registry: DeepDict(known={})}))
    original = deepcopy(metadata)
    nwbfile = mock_NWBFile()
    field = "electrode_metadata_key" if registry == "IntracellularElectrodes" else "series_metadata_key"

    with pytest.raises(ValueError) as error:
        if registry == "IntracellularElectrodes":
            _add_intracellular_electrode_to_nwbfile(nwbfile, metadata, electrode_metadata_key="selected")
        elif registry == "PatchClampSeries":
            _IcephysInterface().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata)
        else:
            _add_patch_clamp_series_to_nwbfile(
                nwbfile, metadata, "selected", series_data=None, electrode=None, mode="current_clamp", is_stimulus=True
            )

    assert str(error.value) == (
        f"{field} 'selected' was not found in metadata['Icephys']['{registry}'] (available keys: ['known'])."
    )
    assert metadata == original
