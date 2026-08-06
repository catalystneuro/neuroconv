"""The contract of the old-to-new metadata translation.

The end-to-end proof that translation preserves what a user stated lives in the old-format
compatibility suites (`tests/test_modalities/test_*/test_*_old_metadata_compatibility.py`), which write
real files and read the values back. What is pinned here is the part of the contract those cannot see:
that the caller's dictionary survives untouched, that a device described twice becomes one entry rather
than two that collide on name, and that translating an already-translated dictionary changes nothing,
which matters because the entry points nest and the same metadata reaches the translator more than once
per conversion.

Delete with the old format.
"""

from neuroconv.utils import DeepDict
from neuroconv.utils._metadata_translation import _translate_old_metadata


def _old_format_metadata() -> dict:
    return {
        "Ecephys": {
            "Device": [{"name": "MyAcquisitionSystem", "description": "A system I described"}],
            "ElectrodeGroup": [
                {"name": "s1", "description": "Shank 1", "location": "CA1", "device": "MyAcquisitionSystem"}
            ],
            "ElectricalSeries": {"name": "ElectricalSeriesRaw", "description": "Raw traces I described"},
        }
    }


class TestTranslationContract:
    def test_the_callers_dictionary_is_not_modified(self):
        metadata = _old_format_metadata()

        _translate_old_metadata(metadata, es_key="ElectricalSeries", metadata_key="my_recording")

        assert set(metadata["Ecephys"]) == {"Device", "ElectrodeGroup", "ElectricalSeries"}
        assert metadata["Ecephys"]["Device"] == [{"name": "MyAcquisitionSystem", "description": "A system I described"}]
        assert "Devices" not in metadata

    def test_old_blocks_do_not_survive_into_the_translated_dictionary(self):
        # The modality blocks are declared with `additionalProperties: False`, so a leftover `Device`
        # would make metadata NeuroConv itself produced fail NeuroConv's own schema.
        translated = _translate_old_metadata(_old_format_metadata())

        assert set(translated["Ecephys"]) == {"ElectrodeGroups", "ElectricalSeries"}

    def test_a_group_link_by_name_becomes_a_link_by_key(self):
        translated = _translate_old_metadata(_old_format_metadata())

        device_key = translated["Ecephys"]["ElectrodeGroups"]["s1"]["device_metadata_key"]
        assert translated["Devices"][device_key]["name"] == "MyAcquisitionSystem"
        assert translated["Devices"][device_key]["description"] == "A system I described"

    def test_a_group_naming_a_device_the_metadata_does_not_describe_gets_one(self):
        # Legal in the old format, where the writer generated the device rather than failing.
        metadata = {"Ecephys": {"ElectrodeGroup": [{"name": "s1", "device": "AnUndescribedSystem"}]}}

        translated = _translate_old_metadata(metadata)

        device_key = translated["Ecephys"]["ElectrodeGroups"]["s1"]["device_metadata_key"]
        assert translated["Devices"][device_key] == {"name": "AnUndescribedSystem"}

    def test_a_device_described_in_both_shapes_becomes_one_entry(self):
        # What a converter produces today: a dict-shaped registry entry carrying fields the list entry
        # lacks, beside the list entry for the same physical device. Keying the list entry by its own
        # name would give two entries with one name, which the duplicate-name check rejects.
        metadata = {
            "Devices": {"neuropixels_imec0": {"name": "NeuropixelsImec0", "manufacturer": "Imec"}},
            "Ecephys": {
                "Device": [{"name": "NeuropixelsImec0", "serial_number": "18194809281"}],
                "ElectrodeGroup": [{"name": "s1", "device": "NeuropixelsImec0"}],
            },
        }

        translated = _translate_old_metadata(metadata)

        assert list(translated["Devices"]) == ["neuropixels_imec0"]
        assert translated["Devices"]["neuropixels_imec0"] == {
            "name": "NeuropixelsImec0",
            "manufacturer": "Imec",
            "serial_number": "18194809281",
        }
        assert translated["Ecephys"]["ElectrodeGroups"]["s1"]["device_metadata_key"] == "neuropixels_imec0"

    def test_translating_twice_changes_nothing(self):
        # The entry points nest, so a dictionary reaches the translator two or three times per conversion.
        once = _translate_old_metadata(_old_format_metadata(), metadata_key="my_recording")
        twice = _translate_old_metadata(once, metadata_key="my_recording")

        assert twice == once

    def test_dict_format_metadata_is_returned_unchanged(self):
        metadata = {
            "Devices": {"my_device": {"name": "MyAcquisitionSystem"}},
            "Ecephys": {
                "ElectrodeGroups": {"s1": {"name": "s1", "device_metadata_key": "my_device"}},
                "ElectricalSeries": {"my_recording": {"name": "ElectricalSeriesRaw"}},
            },
        }

        assert _translate_old_metadata(metadata) is metadata

    def test_an_es_key_entry_is_filed_under_the_metadata_key(self):
        metadata = {
            "Ecephys": {
                "Device": [{"name": "MyAcquisitionSystem"}],
                "ElectricalSeriesAP": {"name": "ElectricalSeriesAP"},
            }
        }

        translated = _translate_old_metadata(metadata, es_key="ElectricalSeriesAP", metadata_key="spikeglx_imec0_ap")

        assert list(translated["Ecephys"]["ElectricalSeries"]) == ["spikeglx_imec0_ap"]
        assert translated["Ecephys"]["ElectricalSeries"]["spikeglx_imec0_ap"]["name"] == "ElectricalSeriesAP"

    def test_an_es_key_entry_keeps_its_key_when_no_label_is_given(self):
        # What validation does, and what a direct caller who passed only `es_key` gets.
        metadata = {
            "Ecephys": {
                "Device": [{"name": "MyAcquisitionSystem"}],
                "ElectricalSeriesAP": {"name": "ElectricalSeriesAP"},
            }
        }

        translated = _translate_old_metadata(metadata)

        assert list(translated["Ecephys"]["ElectricalSeries"]) == ["ElectricalSeriesAP"]

    def test_a_stray_field_beside_real_entries_is_left_for_the_schema_to_reject(self):
        # An old-format edit written onto dict-format metadata. Converting it would guess at what the
        # user meant; leaving it lets validation say so.
        metadata = {
            "Ecephys": {
                "ElectricalSeries": {"my_recording": {"name": "ElectricalSeries"}, "name": "ElectricalSeriesRaw"}
            }
        }

        assert _translate_old_metadata(metadata) is metadata

    def test_a_deep_dict_stays_a_deep_dict(self):
        translated = _translate_old_metadata(DeepDict(_old_format_metadata()))

        assert isinstance(translated, DeepDict)

    def test_the_legacy_list_valued_registry_becomes_keyed(self):
        metadata = {"Devices": [{"name": "MyAcquisitionSystem", "description": "A system I described"}]}

        translated = _translate_old_metadata(metadata)

        assert translated["Devices"] == {
            "MyAcquisitionSystem": {"name": "MyAcquisitionSystem", "description": "A system I described"}
        }


def _old_format_ophys_metadata() -> dict:
    return {
        "Ophys": {
            "Device": [{"name": "MyMicroscope", "description": "A microscope I described"}],
            "ImagingPlane": [
                {"name": "ImagingPlaneGreen", "indicator": "GCaMP6f", "location": "CA1", "device": "MyMicroscope"}
            ],
            "TwoPhotonSeries": [{"name": "TwoPhotonSeriesGreen", "imaging_plane": "ImagingPlaneGreen"}],
            "ImageSegmentation": {
                "name": "ImageSegmentation",
                "plane_segmentations": [
                    {"name": "MySegmentation", "description": "ROIs I described", "imaging_plane": "ImagingPlaneGreen"}
                ],
            },
            "Fluorescence": {
                "name": "Fluorescence",
                "MySegmentation": {"raw": {"name": "RoiResponseSeries", "description": "Raw traces I described"}},
            },
            "DfOverF": {
                "name": "DfOverF",
                "MySegmentation": {"dff": {"name": "RoiResponseSeries", "description": "The df/F traces"}},
            },
            "SegmentationImages": {
                "name": "SegmentationImages",
                "MySegmentation": {"correlation": {"name": "my_correlation_image"}},
            },
        }
    }


class TestOphysTranslationContract:
    def test_the_callers_dictionary_is_not_modified(self):
        metadata = _old_format_ophys_metadata()

        _translate_old_metadata(metadata, metadata_key="my_series", photon_series_type="TwoPhotonSeries")

        assert "TwoPhotonSeries" in metadata["Ophys"]
        assert "Devices" not in metadata

    def test_links_by_name_become_links_by_key(self):
        translated = _translate_old_metadata(_old_format_ophys_metadata())

        plane = translated["Ophys"]["ImagingPlanes"]["ImagingPlaneGreen"]
        assert translated["Devices"][plane["device_metadata_key"]]["name"] == "MyMicroscope"
        assert "device" not in plane

        series = translated["Ophys"]["MicroscopySeries"]["TwoPhotonSeriesGreen"]
        assert series["imaging_plane_metadata_key"] == "ImagingPlaneGreen"

        segmentation = translated["Ophys"]["PlaneSegmentations"]["MySegmentation"]
        assert segmentation["imaging_plane_metadata_key"] == "ImagingPlaneGreen"

    def test_the_addressed_photon_series_is_filed_under_the_metadata_key(self):
        translated = _translate_old_metadata(
            _old_format_ophys_metadata(),
            metadata_key="my_series",
            photon_series_type="TwoPhotonSeries",
            photon_series_index=0,
        )

        assert list(translated["Ophys"]["MicroscopySeries"]) == ["my_series"]
        assert translated["Ophys"]["MicroscopySeries"]["my_series"]["name"] == "TwoPhotonSeriesGreen"

    def test_the_addressed_plane_segmentation_rekeys_its_traces_and_images(self):
        # Traces and summary images are keyed by the plane segmentation's key, so re-keying it has to
        # carry them along or they are looked up under a key that no longer exists.
        translated = _translate_old_metadata(
            _old_format_ophys_metadata(), metadata_key="my_segmentation", plane_segmentation_name="MySegmentation"
        )

        assert list(translated["Ophys"]["PlaneSegmentations"]) == ["my_segmentation"]
        assert list(translated["Ophys"]["RoiResponses"]) == ["my_segmentation"]
        assert list(translated["Ophys"]["SegmentationImages"]) == ["my_segmentation"]

    def test_the_two_trace_containers_merge_into_one_block(self):
        translated = _translate_old_metadata(_old_format_ophys_metadata())

        traces = translated["Ophys"]["RoiResponses"]["MySegmentation"]
        assert set(traces) == {"raw", "dff"}
        assert traces["raw"]["description"] == "Raw traces I described"
        assert traces["dff"]["description"] == "The df/F traces"

    def test_a_trace_name_that_only_worked_in_two_containers_is_renamed(self):
        # The old defaults name both the raw and the df/F trace `RoiResponseSeries`, which was legal
        # while they lived in separate containers. One container means one namespace.
        translated = _translate_old_metadata(_old_format_ophys_metadata())

        traces = translated["Ophys"]["RoiResponses"]["MySegmentation"]
        assert traces["raw"]["name"] == "RoiResponseSeries"
        assert traces["dff"]["name"] == "DfOverF"

    def test_summary_images_the_caller_did_not_mention_are_still_declared(self):
        # The old writer wrote whichever images the extractor had, whether or not metadata named them.
        translated = _translate_old_metadata(_old_format_ophys_metadata())

        images = translated["Ophys"]["SegmentationImages"]["MySegmentation"]
        assert images["correlation"]["name"] == "my_correlation_image"
        assert images["mean"]["name"] == "mean_image"

    def test_dict_format_ophys_metadata_is_returned_unchanged(self):
        metadata = {
            "Devices": {"my_microscope": {"name": "MyMicroscope"}},
            "Ophys": {
                "ImagingPlanes": {"my_plane": {"name": "ImagingPlane", "device_metadata_key": "my_microscope"}},
                "MicroscopySeries": {
                    "my_series": {"name": "TwoPhotonSeries", "imaging_plane_metadata_key": "my_plane"}
                },
            },
        }

        assert _translate_old_metadata(metadata) is metadata

    def test_translating_twice_changes_nothing(self):
        once = _translate_old_metadata(_old_format_ophys_metadata())
        twice = _translate_old_metadata(once)

        assert twice == once

    def test_an_extractor_with_no_traces_still_converts(self):
        # The old defaults declare six trace roles on every segmentation, so translated metadata asks for
        # traces from extractors that have none (`InscopixSegmentationInterface` among them). The dict
        # writer rejects a request it cannot satisfy, which is right for metadata someone wrote and wrong
        # for boilerplate, so the translated block is dropped and the conversion writes nothing for it,
        # which is what the old writer did.
        from datetime import datetime

        from neuroconv.tools.testing.mock_interfaces import MockSegmentationInterface

        interface = MockSegmentationInterface(
            has_raw_signal=False, has_dff_signal=False, has_deconvolved_signal=False, has_neuropil_signal=False
        )
        metadata = interface.get_metadata(use_new_metadata_format=False)
        metadata["NWBFile"].update(session_start_time=datetime(2020, 1, 1).astimezone())

        nwbfile = interface.create_nwbfile(metadata=metadata)

        assert "Fluorescence" not in nwbfile.processing["ophys"].data_interfaces
        assert "ImageSegmentation" in nwbfile.processing["ophys"].data_interfaces
