.. _metadata_structures:

Metadata Structures
====================

This guide describes the internal metadata structures used by NeuroConv for different data modalities. Understanding these structures is essential for developers working on data interfaces and conversion tools.

Optical Physiology (Ophys) Metadata
------------------------------------

The optical physiology metadata uses a dictionary-based structure that improves organization and supports multiple recording regions or analysis pipelines within a single conversion.

Dictionary-Based Structure
^^^^^^^^^^^^^^^^^^^^^^^^^^

The ophys metadata structure uses dictionaries keyed by ``metadata_key``. This provides several advantages:

1. **Semantic naming**: Components are referenced by meaningful names rather than array indices
2. **Single key propagation**: One ``metadata_key`` per interface manages all related components
3. **Flexible organization**: Easy to handle multiple brain regions, recording sessions, or analysis pipelines

Key Components
^^^^^^^^^^^^^^

Default Metadata Structure
~~~~~~~~~~~~~~~~~~~~~~~~~~~

When interfaces are created, they generate default metadata with their ``metadata_key``. Here's how the metadata is structured for imaging and segmentation interfaces:

**Devices and ImagingPlanes (shared defaults):**

.. code-block:: python

    # Devices are created with default keys and can be shared across interfaces
    metadata["Devices"] = {
        "default_device_metadata_key": {
            "name": "Device",
            "description": "The device used for recording"
        }
    }

    # ImagingPlanes use default keys that multiple interfaces can reference
    metadata["Ophys"]["ImagingPlanes"] = {
        "default_imaging_plane_metadata_key": {
            "name": "ImagingPlane",
            "description": "The plane or volume being imaged by the microscope.",
            "indicator": "unknown",
            "location": "unknown",
            "device_metadata_key": "default_device_metadata_key",  # References device by key
            "optical_channel": [
                {
                    "name": "channel_num_0",
                    "description": "An optical channel of the microscope."
                }
            ]
        }
    }

**Imaging Interface Metadata:**

When you create imaging interfaces with specific ``metadata_key`` values, they populate the PhotonSeries:

.. code-block:: python

    # Two imaging interfaces with different metadata_keys
    imaging_key_1 = "visual_cortex"
    imaging_key_2 = "hippocampus"

    metadata["Ophys"]["TwoPhotonSeries"] = {
        imaging_key_1: {  # Key from first imaging interface
            "name": "TwoPhotonSeries",
            "description": "Imaging data from two-photon excitation microscopy.",
            "unit": "n.a.",
            "imaging_plane_metadata_key": "default_imaging_plane_metadata_key",  # Links to default plane
            "dimension": [512, 512]
        },
        imaging_key_2: {  # Key from second imaging interface
            "name": "TwoPhotonSeries",  # Can have same name (will be made unique later)
            "description": "Imaging data from two-photon excitation microscopy.",
            "unit": "n.a.",
            "imaging_plane_metadata_key": "default_imaging_plane_metadata_key",  # Also links to default plane
            "dimension": [256, 256]
        }
    }

**Segmentation Interface Metadata:**

When you create segmentation interfaces with specific ``metadata_key`` values, they populate multiple components:

.. code-block:: python

    # Two segmentation interfaces with different metadata_keys
    segmentation_key_1 = "suite2p_analysis"
    segmentation_key_2 = "caiman_analysis"

    # ImageSegmentation contains PlaneSegmentation for each interface
    metadata["Ophys"]["ImageSegmentation"] = {
        "name": "ImageSegmentation",  # Container name
        segmentation_key_1: {  # Key from first segmentation interface
            "name": "PlaneSegmentation",
            "description": "Segmented ROIs from Suite2p",
            "imaging_plane_metadata_key": "default_imaging_plane_metadata_key"
        },
        segmentation_key_2: {  # Key from second segmentation interface
            "name": "PlaneSegmentation",
            "description": "Segmented ROIs from CaImAn",
            "imaging_plane_metadata_key": "default_imaging_plane_metadata_key"
        }
    }

    # Fluorescence traces are organized by the same metadata_key
    metadata["Ophys"]["Fluorescence"] = {
        "name": "Fluorescence",
        segmentation_key_1: {  # Matches first segmentation interface
            "raw": {
                "name": "RoiResponseSeries",
                "description": "Array of raw fluorescence traces.",
                "unit": "n.a."
            },
            "neuropil": {
                "name": "Neuropil",
                "description": "Neuropil traces from Suite2p"
            },
            "deconvolved": {
                "name": "Deconvolved",
                "description": "Deconvolved traces from Suite2p"
            }
        },
        segmentation_key_2: {  # Matches second segmentation interface
            "raw": {
                "name": "RoiResponseSeries",
                "description": "Array of raw fluorescence traces.",
                "unit": "n.a."
            },
            "neuropil": {
                "name": "Neuropil",
                "description": "Neuropil traces from CaImAn"
            },
            "deconvolved": {
                "name": "Deconvolved",
                "description": "Deconvolved traces from CaImAn"
            }
        }
    }

    # DfOverF traces follow the same pattern
    metadata["Ophys"]["DfOverF"] = {
        "name": "DfOverF",
        segmentation_key_1: {  # Matches first segmentation interface
            "dff": {
                "name": "RoiResponseSeries",
                "description": "Array of df/F traces from Suite2p.",
                "unit": "n.a."
            }
        },
        segmentation_key_2: {  # Matches second segmentation interface
            "dff": {
                "name": "RoiResponseSeries",
                "description": "Array of df/F traces from CaImAn.",
                "unit": "n.a."
            }
        }
    }

    # SegmentationImages also use the same keys
    metadata["Ophys"]["SegmentationImages"] = {
        "name": "SegmentationImages",
        "description": "The summary images of the segmentation.",
        segmentation_key_1: {  # Matches first segmentation interface
            "correlation": {
                "name": f"correlation_{segmentation_key_1}",  # Unique name includes key
                "description": "The correlation image from Suite2p."
            },
            "mean": {
                "name": f"mean_{segmentation_key_1}",
                "description": "The mean image from Suite2p."
            }
        },
        segmentation_key_2: {  # Matches second segmentation interface
            "correlation": {
                "name": f"correlation_{segmentation_key_2}",  # Unique name includes key
                "description": "The correlation image from CaImAn."
            },
            "mean": {
                "name": f"mean_{segmentation_key_2}",
                "description": "The mean image from CaImAn."
            }
        }
    }

Customizing Imaging Plane Links
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By default, all interfaces link to ``"default_imaging_plane_metadata_key"``. To create separate imaging planes for different regions:

.. code-block:: python

    # Step 1: Add new imaging plane entries with unique keys
    visual_cortex_plane_key = "visual_cortex_plane"
    hippocampus_plane_key = "hippocampus_plane"

    # Add device entries for each plane
    metadata["Devices"]["visual_cortex_device"] = {
        "name": "VisualCortexMicroscope",
        "description": "Two-photon microscope for visual cortex"
    }
    metadata["Devices"]["hippocampus_device"] = {
        "name": "HippocampusMiniscope",
        "description": "Miniscope for hippocampus imaging"
    }

    # Add new imaging plane entries
    metadata["Ophys"]["ImagingPlanes"][visual_cortex_plane_key] = {
        "name": "ImagingPlaneVisualCortex",
        "description": "Visual cortex imaging plane",
        "indicator": "GCaMP6f",
        "location": "V1",
        "device_metadata_key": "visual_cortex_device",
        "excitation_lambda": 920.0,
        "optical_channel": [
            {
                "name": "green_channel",
                "description": "Green channel",
                "emission_lambda": 520.0
            }
        ]
    }

    metadata["Ophys"]["ImagingPlanes"][hippocampus_plane_key] = {
        "name": "ImagingPlaneHippocampus",
        "description": "Hippocampus imaging plane",
        "indicator": "GCaMP7f",
        "location": "CA1",
        "device_metadata_key": "hippocampus_device",
        "excitation_lambda": 488.0,
        "optical_channel": [
            {
                "name": "blue_channel",
                "description": "Blue channel",
                "emission_lambda": 510.0
            }
        ]
    }

    # Step 2: Update the PhotonSeries to reference the new planes
    metadata["Ophys"]["TwoPhotonSeries"]["visual_cortex"]["imaging_plane_metadata_key"] = visual_cortex_plane_key
    metadata["Ophys"]["TwoPhotonSeries"]["hippocampus"]["imaging_plane_metadata_key"] = hippocampus_plane_key

    # Step 3: Update PlaneSegmentations to reference appropriate planes
    metadata["Ophys"]["ImageSegmentation"]["suite2p_analysis"]["imaging_plane_metadata_key"] = visual_cortex_plane_key
    metadata["Ophys"]["ImageSegmentation"]["caiman_analysis"]["imaging_plane_metadata_key"] = hippocampus_plane_key

Single metadata_key per Interface
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Each data interface uses a single ``metadata_key`` parameter that propagates to all components it creates:

.. code-block:: python

    # Imaging interface
    imaging_interface = ScanImageImagingInterface(
        file_path="data.tif",
        metadata_key="visual_cortex"  # Single key for all components
    )

    # This creates:
    # - ImagingPlanes["visual_cortex"]
    # - TwoPhotonSeries["visual_cortex"]
    # - Device references use "visual_cortex"

    # Segmentation interface
    segmentation_interface = Suite2pSegmentationInterface(
        folder_path="suite2p_output/",
        metadata_key="visual_cortex_suite2p"  # Different key for this analysis
    )

    # This creates:
    # - ImageSegmentation["visual_cortex_suite2p"]
    # - References ImagePlane by the key from the imaging interface

Multi-Region Example
^^^^^^^^^^^^^^^^^^^^

Here's how to organize metadata for a multi-region experiment:

.. code-block:: python

    # Visual cortex 2-photon imaging
    visual_imaging = ScanImageImagingInterface(
        file_path="visual_cortex.tif",
        metadata_key="visual_cortex"
    )

    # Hippocampus 1-photon imaging
    hippocampus_imaging = MiniscopeImagingInterface(
        folder_path="miniscope_data/",
        metadata_key="hippocampus"
    )

    # Suite2p analysis of visual cortex
    visual_segmentation = Suite2pSegmentationInterface(
        folder_path="suite2p_visual/",
        metadata_key="visual_cortex_suite2p"
    )

    # CaImAn analysis of hippocampus
    hippocampus_segmentation = CaimanSegmentationInterface(
        file_path="caiman_results.hdf5",
        metadata_key="hippocampus_caiman"
    )

This creates a well-organized metadata structure:

.. code-block:: python

    metadata = {
        "Ophys": {
            "ImagingPlanes": {
                "visual_cortex": {...},
                "hippocampus": {...}
            },
            "TwoPhotonSeries": {
                "visual_cortex": {...}
            },
            "OnePhotonSeries": {
                "hippocampus": {...}
            },
            "ImageSegmentation": {
                "name": "ImageSegmentation",
                "visual_cortex_suite2p": {...},
                "hippocampus_caiman": {...}
            }
        }
    }


Schema Validation
^^^^^^^^^^^^^^^^^

The JSON schemas validate the dictionary structure:

.. code-block:: python

    # ImageSegmentation schema supports both top-level name and keyed entries
    image_segmentation_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"}  # Container name
        },
        "patternProperties": {
            "^(?!name$)[a-zA-Z0-9_]+$": {  # Excludes "name" key
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "imaging_plane_key": {"type": "string"}  # References by key
                },
                "required": ["name", "imaging_plane_key"]
            }
        }
    }

Best Practices
^^^^^^^^^^^^^^

When working with the new ophys metadata structure:

1. **Use descriptive metadata_keys**: Choose meaningful names like ``"visual_cortex"``, ``"ca1_region"``, ``"suite2p_analysis"``

2. **Single key per interface**: Each interface should use one ``metadata_key`` that propagates to all its components

3. **Consistent referencing**: Always reference components by their ``metadata_key``, not by their ``name`` field

4. **Avoid hardcoded indices**: Never use array indices like ``[0]`` - use the dictionary keys instead

This structure provides a more maintainable and extensible foundation for handling complex optical physiology experiments with multiple recording regions and analysis pipelines.
