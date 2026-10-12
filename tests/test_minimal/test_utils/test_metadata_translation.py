"""The contract of the old-to-new metadata translation.

The end-to-end proof that translation preserves what a user stated lives in the old-format
compatibility suites (`tests/test_modalities/test_*/test_*_old_metadata_compatibility.py`), which write
real files and read the values back. What is pinned here is the part of the contract those cannot see:
that the caller's dictionary survives untouched, that a device described twice becomes one entry rather
than two that collide on name, and that translating an already-translated dictionary changes nothing,
which matters because the entry points nest and the same metadata reaches the translator more than once
per conversion.

Each test states the dictionary it expects in full and compares the whole thing, rather than reaching for
the fields it cares about. A translation is a whole-dictionary transformation, so the interesting failures
are the entries that quietly went missing, and those are exactly what a targeted assertion cannot see.

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

        assert metadata == _old_format_metadata()

    def test_old_format_metadata_becomes_the_dict_format(self):
        # The devices move to the top-level registry and the group's link by name becomes a link by key.
        # The old blocks do not survive: the modality blocks are declared with `additionalProperties: False`,
        # so a leftover `Device` would make metadata NeuroConv itself produced fail NeuroConv's own schema.
        expected_translated_metadata = {
            "Devices": {"MyAcquisitionSystem": {"name": "MyAcquisitionSystem", "description": "A system I described"}},
            "Ecephys": {
                "ElectrodeGroups": {
                    "s1": {
                        "name": "s1",
                        "description": "Shank 1",
                        "location": "CA1",
                        "device_metadata_key": "MyAcquisitionSystem",
                    }
                },
                "ElectricalSeries": {
                    "ElectricalSeries": {"name": "ElectricalSeriesRaw", "description": "Raw traces I described"}
                },
            },
        }

        assert _translate_old_metadata(_old_format_metadata()) == expected_translated_metadata

    def test_a_group_naming_a_device_the_metadata_does_not_describe_gets_one(self):
        # Legal in the old format, where the writer generated the device rather than failing.
        metadata = {"Ecephys": {"ElectrodeGroup": [{"name": "s1", "device": "AnUndescribedSystem"}]}}
        expected_translated_metadata = {
            "Devices": {"AnUndescribedSystem": {"name": "AnUndescribedSystem"}},
            "Ecephys": {"ElectrodeGroups": {"s1": {"name": "s1", "device_metadata_key": "AnUndescribedSystem"}}},
        }

        assert _translate_old_metadata(metadata) == expected_translated_metadata

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
        expected_translated_metadata = {
            "Devices": {
                "neuropixels_imec0": {
                    "name": "NeuropixelsImec0",
                    "manufacturer": "Imec",
                    "serial_number": "18194809281",
                }
            },
            "Ecephys": {"ElectrodeGroups": {"s1": {"name": "s1", "device_metadata_key": "neuropixels_imec0"}}},
        }

        assert _translate_old_metadata(metadata) == expected_translated_metadata

    def test_translating_twice_changes_nothing(self):
        # The entry points nest, so a dictionary reaches the translator two or three times per conversion.
        expected_translated_metadata = {
            "Devices": {"MyAcquisitionSystem": {"name": "MyAcquisitionSystem", "description": "A system I described"}},
            "Ecephys": {
                "ElectrodeGroups": {
                    "s1": {
                        "name": "s1",
                        "description": "Shank 1",
                        "location": "CA1",
                        "device_metadata_key": "MyAcquisitionSystem",
                    }
                },
                "ElectricalSeries": {
                    "my_recording": {"name": "ElectricalSeriesRaw", "description": "Raw traces I described"}
                },
            },
        }

        once = _translate_old_metadata(_old_format_metadata(), metadata_key="my_recording")
        twice = _translate_old_metadata(once, metadata_key="my_recording")

        assert once == expected_translated_metadata
        assert twice == expected_translated_metadata

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
        expected_translated_metadata = {
            "Devices": {"MyAcquisitionSystem": {"name": "MyAcquisitionSystem"}},
            "Ecephys": {"ElectricalSeries": {"spikeglx_imec0_ap": {"name": "ElectricalSeriesAP"}}},
        }

        translated = _translate_old_metadata(metadata, es_key="ElectricalSeriesAP", metadata_key="spikeglx_imec0_ap")

        assert translated == expected_translated_metadata

    def test_an_es_key_entry_keeps_its_key_when_no_label_is_given(self):
        # What validation does, and what a direct caller who passed only `es_key` gets.
        metadata = {
            "Ecephys": {
                "Device": [{"name": "MyAcquisitionSystem"}],
                "ElectricalSeriesAP": {"name": "ElectricalSeriesAP"},
            }
        }
        expected_translated_metadata = {
            "Devices": {"MyAcquisitionSystem": {"name": "MyAcquisitionSystem"}},
            "Ecephys": {"ElectricalSeries": {"ElectricalSeriesAP": {"name": "ElectricalSeriesAP"}}},
        }

        assert _translate_old_metadata(metadata) == expected_translated_metadata

    def test_dict_shaped_entries_survive_an_old_block_beside_them(self):
        # The upgrade edit, and what the switch release's guard promises to convert rather than ignore: an
        # old-format `Device` line written onto dict-format metadata. The groups the interface read out of
        # the source are already dict-shaped, so building the block out of the old keys alone loses their
        # descriptions, locations and device links, and the conversion writes placeholders instead without
        # raising anything.
        metadata = {
            "Devices": {"probe": {"name": "Neuropixels", "description": "read from the header"}},
            "Ecephys": {
                "ElectrodeGroups": {
                    "s1": {"name": "s1", "description": "Shank 1", "location": "CA1", "device_metadata_key": "probe"}
                },
                "ElectricalSeries": {"my_recording": {"name": "ElectricalSeriesRaw"}},
                "Device": [{"name": "MyProbe", "description": "The probe I described"}],
            },
        }
        expected_translated_metadata = {
            "Devices": {
                "probe": {"name": "Neuropixels", "description": "read from the header"},
                # The old entry is translated beside the dict-shaped one rather than in place of it.
                "MyProbe": {"name": "MyProbe", "description": "The probe I described"},
            },
            "Ecephys": {
                "ElectrodeGroups": {
                    "s1": {"name": "s1", "description": "Shank 1", "location": "CA1", "device_metadata_key": "probe"}
                },
                "ElectricalSeries": {"my_recording": {"name": "ElectricalSeriesRaw"}},
            },
        }

        assert _translate_old_metadata(metadata) == expected_translated_metadata

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
        expected_translated_metadata = {
            "Devices": {"MyAcquisitionSystem": {"name": "MyAcquisitionSystem", "description": "A system I described"}}
        }

        assert _translate_old_metadata(metadata) == expected_translated_metadata


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

        assert metadata == _old_format_ophys_metadata()

    def test_old_format_ophys_metadata_becomes_the_dict_format(self):
        expected_translated_metadata = {
            "Devices": {"MyMicroscope": {"name": "MyMicroscope", "description": "A microscope I described"}},
            "Ophys": {
                # Links by name become links by key, on the plane, the series and the plane segmentation.
                "ImagingPlanes": {
                    "ImagingPlaneGreen": {
                        "name": "ImagingPlaneGreen",
                        "indicator": "GCaMP6f",
                        "location": "CA1",
                        "device_metadata_key": "MyMicroscope",
                    }
                },
                "MicroscopySeries": {
                    "TwoPhotonSeriesGreen": {
                        "name": "TwoPhotonSeriesGreen",
                        "imaging_plane_metadata_key": "ImagingPlaneGreen",
                    }
                },
                "PlaneSegmentations": {
                    "MySegmentation": {
                        "name": "MySegmentation",
                        "description": "ROIs I described",
                        "imaging_plane_metadata_key": "ImagingPlaneGreen",
                    }
                },
                # `Fluorescence` and `DfOverF` merge into one block keyed by role. The old defaults name
                # both the raw and the df/F trace `RoiResponseSeries`, which was legal while they lived in
                # separate containers; one container means one namespace, so the later role is renamed to
                # the dict format's own name for it.
                "RoiResponses": {
                    "MySegmentation": {
                        "raw": {"name": "RoiResponseSeries", "description": "Raw traces I described"},
                        "dff": {"name": "DfOverF", "description": "The df/F traces"},
                    }
                },
                # The old writer wrote whichever images the extractor had, whether or not metadata named
                # them, so `mean` is declared even though the caller only mentioned `correlation`.
                "SegmentationImages": {
                    "MySegmentation": {
                        "correlation": {"name": "my_correlation_image"},
                        "mean": {"name": "mean_image"},
                    }
                },
            },
        }

        assert _translate_old_metadata(_old_format_ophys_metadata()) == expected_translated_metadata

    def test_the_addressed_photon_series_is_filed_under_the_metadata_key(self):
        expected_translated_metadata = {
            "Devices": {"MyMicroscope": {"name": "MyMicroscope", "description": "A microscope I described"}},
            "Ophys": {
                "ImagingPlanes": {
                    "ImagingPlaneGreen": {
                        "name": "ImagingPlaneGreen",
                        "indicator": "GCaMP6f",
                        "location": "CA1",
                        "device_metadata_key": "MyMicroscope",
                    }
                },
                "MicroscopySeries": {
                    "my_series": {"name": "TwoPhotonSeriesGreen", "imaging_plane_metadata_key": "ImagingPlaneGreen"}
                },
                "PlaneSegmentations": {
                    "MySegmentation": {
                        "name": "MySegmentation",
                        "description": "ROIs I described",
                        "imaging_plane_metadata_key": "ImagingPlaneGreen",
                    }
                },
                "RoiResponses": {
                    "MySegmentation": {
                        "raw": {"name": "RoiResponseSeries", "description": "Raw traces I described"},
                        "dff": {"name": "DfOverF", "description": "The df/F traces"},
                    }
                },
                "SegmentationImages": {
                    "MySegmentation": {
                        "correlation": {"name": "my_correlation_image"},
                        "mean": {"name": "mean_image"},
                    }
                },
            },
        }

        translated = _translate_old_metadata(
            _old_format_ophys_metadata(),
            metadata_key="my_series",
            photon_series_type="TwoPhotonSeries",
            photon_series_index=0,
        )

        assert translated == expected_translated_metadata

    def test_the_addressed_plane_segmentation_rekeys_its_traces_and_images(self):
        # Traces and summary images are keyed by the plane segmentation's key, so re-keying it has to
        # carry them along or they are looked up under a key that no longer exists.
        expected_translated_metadata = {
            "Devices": {"MyMicroscope": {"name": "MyMicroscope", "description": "A microscope I described"}},
            "Ophys": {
                "ImagingPlanes": {
                    "ImagingPlaneGreen": {
                        "name": "ImagingPlaneGreen",
                        "indicator": "GCaMP6f",
                        "location": "CA1",
                        "device_metadata_key": "MyMicroscope",
                    }
                },
                "MicroscopySeries": {
                    "TwoPhotonSeriesGreen": {
                        "name": "TwoPhotonSeriesGreen",
                        "imaging_plane_metadata_key": "ImagingPlaneGreen",
                    }
                },
                "PlaneSegmentations": {
                    "my_segmentation": {
                        "name": "MySegmentation",
                        "description": "ROIs I described",
                        "imaging_plane_metadata_key": "ImagingPlaneGreen",
                    }
                },
                "RoiResponses": {
                    "my_segmentation": {
                        "raw": {"name": "RoiResponseSeries", "description": "Raw traces I described"},
                        "dff": {"name": "DfOverF", "description": "The df/F traces"},
                    }
                },
                "SegmentationImages": {
                    "my_segmentation": {
                        "correlation": {"name": "my_correlation_image"},
                        "mean": {"name": "mean_image"},
                    }
                },
            },
        }

        translated = _translate_old_metadata(
            _old_format_ophys_metadata(), metadata_key="my_segmentation", plane_segmentation_name="MySegmentation"
        )

        assert translated == expected_translated_metadata

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

    def test_dict_shaped_entries_survive_an_old_block_beside_them(self):
        # What a converter hands every interface today when a dict-only one (`BrukerTiffImagingInterface`)
        # shares a dictionary with a dual-mode one: a single `Ophys` block holding both shapes. Building
        # the block out of the old keys alone drops the dict-only interface's own entries, and the writer
        # then falls back to the placeholder template, whose device carries the name the translated list
        # already registered, so the duplicate-name check rejects a dictionary the user never wrote.
        metadata = {
            "Devices": {"bruker_device": {"name": "BrukerFluorescenceMicroscope"}},
            "Ophys": {
                "ImagingPlanes": {"bruker": {"name": "ImagingPlane", "device_metadata_key": "bruker_device"}},
                "MicroscopySeries": {"bruker": {"name": "TwoPhotonSeries", "imaging_plane_metadata_key": "bruker"}},
                "Device": [{"name": "Microscope"}],
                "ImagingPlane": [{"name": "ImagingPlaneChan1Plane0", "device": "Microscope"}],
                "ImageSegmentation": {
                    "plane_segmentations": [{"name": "PlaneSegmentation", "imaging_plane": "ImagingPlaneChan1Plane0"}]
                },
            },
        }
        expected_translated_metadata = {
            "Devices": {
                "bruker_device": {"name": "BrukerFluorescenceMicroscope"},
                "Microscope": {"name": "Microscope"},
            },
            "Ophys": {
                # The old block is translated beside the dict-shaped entries rather than in place of them.
                "ImagingPlanes": {
                    "bruker": {"name": "ImagingPlane", "device_metadata_key": "bruker_device"},
                    "ImagingPlaneChan1Plane0": {
                        "name": "ImagingPlaneChan1Plane0",
                        "device_metadata_key": "Microscope",
                    },
                },
                "MicroscopySeries": {"bruker": {"name": "TwoPhotonSeries", "imaging_plane_metadata_key": "bruker"}},
                "PlaneSegmentations": {
                    "PlaneSegmentation": {
                        "name": "PlaneSegmentation",
                        "imaging_plane_metadata_key": "ImagingPlaneChan1Plane0",
                    }
                },
            },
        }

        assert _translate_old_metadata(metadata) == expected_translated_metadata

    def test_translating_twice_changes_nothing(self):
        once = _translate_old_metadata(_old_format_ophys_metadata())
        twice = _translate_old_metadata(once)

        assert twice == once


class TestCrossModalityTranslationContract:
    """One dictionary carrying both modalities, which is what a converter always hands its interfaces."""

    def test_one_modality_being_old_leaves_the_other_alone(self):
        # A converter pairing a dual-mode ecephys interface, old at today's default, with a dict-only
        # imaging one. The registry is shared, so translating the ecephys block writes into the same place
        # the imaging block's links point at, and rebuilding one modality must not reach into the other.
        metadata = {
            "Devices": {"bruker_device": {"name": "BrukerFluorescenceMicroscope"}},
            "Ophys": {
                "ImagingPlanes": {"bruker": {"name": "ImagingPlane", "device_metadata_key": "bruker_device"}},
                "MicroscopySeries": {"bruker": {"name": "TwoPhotonSeries", "imaging_plane_metadata_key": "bruker"}},
            },
            "Ecephys": {
                "Device": [{"name": "MyAcquisitionSystem", "description": "A system I described"}],
                "ElectrodeGroup": [{"name": "s1", "location": "CA1", "device": "MyAcquisitionSystem"}],
            },
        }
        expected_translated_metadata = {
            "Devices": {
                "bruker_device": {"name": "BrukerFluorescenceMicroscope"},
                "MyAcquisitionSystem": {"name": "MyAcquisitionSystem", "description": "A system I described"},
            },
            "Ophys": {
                "ImagingPlanes": {"bruker": {"name": "ImagingPlane", "device_metadata_key": "bruker_device"}},
                "MicroscopySeries": {"bruker": {"name": "TwoPhotonSeries", "imaging_plane_metadata_key": "bruker"}},
            },
            "Ecephys": {
                "ElectrodeGroups": {
                    "s1": {"name": "s1", "location": "CA1", "device_metadata_key": "MyAcquisitionSystem"}
                }
            },
        }

        assert _translate_old_metadata(metadata) == expected_translated_metadata

    def test_a_device_both_modalities_name_becomes_one_entry(self):
        # `nwbfile.devices` is one namespace, so the two old lists naming the same acquisition system
        # described one device and have to keep describing one after translation. Two entries sharing a
        # name is what the duplicate-name check rejects.
        metadata = {
            "Ecephys": {
                "Device": [{"name": "MyRig", "description": "A rig I described"}],
                "ElectrodeGroup": [{"name": "s1", "device": "MyRig"}],
            },
            "Ophys": {
                "Device": [{"name": "MyRig", "manufacturer": "A manufacturer I stated"}],
                "ImagingPlane": [{"name": "ImagingPlaneGreen", "device": "MyRig"}],
            },
        }
        expected_translated_metadata = {
            "Devices": {
                "MyRig": {
                    "name": "MyRig",
                    "description": "A rig I described",
                    "manufacturer": "A manufacturer I stated",
                }
            },
            "Ecephys": {"ElectrodeGroups": {"s1": {"name": "s1", "device_metadata_key": "MyRig"}}},
            "Ophys": {
                "ImagingPlanes": {"ImagingPlaneGreen": {"name": "ImagingPlaneGreen", "device_metadata_key": "MyRig"}}
            },
        }

        assert _translate_old_metadata(metadata) == expected_translated_metadata
