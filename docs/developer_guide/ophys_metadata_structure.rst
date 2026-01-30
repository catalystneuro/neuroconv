.. _ophys_metadata_structure:

Ophys Metadata Structure
========================

This document describes the architecture of the optical physiology (ophys) metadata system in NeuroConv.
It is intended for developers who are contributing new interfaces or modifying existing ones.

For user-facing documentation on how to annotate ophys data, see :ref:`annotate_ophys_metadata`.


Design Principles
-----------------

The ophys metadata system is built on several core principles:

1. **Dictionary-Based Organization**
   Metadata is organized using dictionaries with meaningful keys. This structure makes metadata
   easier to reference, organize, and extend. Dictionaries allow direct access to specific
   components by name, which is clearer and less error-prone than positional access.

   .. code-block:: python

       metadata["Ophys"]["ImagingPlanes"]["visual_cortex"]["indicator"] = "GCaMP6s"


2. **Consistent metadata_key Across Interfaces**
   Every ophys interface uses a single ``metadata_key`` parameter that propagates to all its
   components (Device, ImagingPlane, PhotonSeries). This provides a consistent pattern across
   all interfaces, making the API predictable and easier to learn.

3. **Explicit References**
   Components reference each other using explicit ``_metadata_key`` fields. This makes
   relationships between components clear and enables validation.

4. **Top-Level Devices**
   Devices are stored at the top level (``metadata["Devices"]``) enabling device sharing
   across ophys, ecephys, and other modalities.

5. **Provenance-First get_metadata()**
   The ``get_metadata()`` method returns only values extracted from the source data, not defaults.
   Defaults are applied at NWB object creation time.


Metadata Structure Overview
---------------------------

The complete ophys metadata structure:

.. code-block:: python

    metadata = {
        "NWBFile": {...},  # Session-level metadata
        "Subject": {...},  # Subject information

        "Devices": {
            "visual_cortex": {
                "name": "Microscope",
                "description": "Two-photon microscope for visual cortex imaging",
                "manufacturer": "Bruker"
            },
            "hippocampus": {
                "name": "Miniscope",
                "description": "UCLA Miniscope v4 for hippocampal imaging"
            }
        },

        "Ophys": {
            "ImagingPlanes": {
                "visual_cortex": {
                    "name": "ImagingPlaneVisualCortex",
                    "description": "Imaging plane in V1 layer 2/3",
                    "device_metadata_key": "visual_cortex",  # Reference to device
                    "excitation_lambda": 920.0,
                    "indicator": "GCaMP6s",
                    "location": "V1 binocular zone",
                    "optical_channel": [
                        {
                            "name": "GreenChannel",
                            "description": "GCaMP emission channel",
                            "emission_lambda": 510.0
                        }
                    ]
                },
                "hippocampus": {
                    "name": "ImagingPlaneHippocampus",
                    "device_metadata_key": "hippocampus",
                    "excitation_lambda": 470.0,
                    "indicator": "GCaMP6f",
                    "location": "CA1 pyramidal layer",
                    "optical_channel": [...]
                }
            },

            "TwoPhotonSeries": {
                "visual_cortex": {
                    "name": "TwoPhotonSeriesVisualCortex",
                    "description": "Two-photon calcium imaging",
                    "imaging_plane_metadata_key": "visual_cortex",  # Reference to imaging plane
                    "unit": "n.a.",
                    "dimension": [512, 512]
                }
            },

            "OnePhotonSeries": {
                "hippocampus": {
                    "name": "OnePhotonSeriesHippocampus",
                    "imaging_plane_metadata_key": "hippocampus",
                    "unit": "n.a.",
                    "dimension": [480, 752]
                }
            },

            "ImageSegmentation": {
                "name": "ImageSegmentation",
                "suite2p_analysis": {
                    "name": "PlaneSegmentation",
                    "description": "ROIs detected by Suite2p",
                    "imaging_plane_metadata_key": "visual_cortex"
                }
            },

            "Fluorescence": {
                "name": "Fluorescence",
                "suite2p_analysis": {
                    "raw": {
                        "name": "RoiResponseSeries",
                        "description": "Raw fluorescence traces",
                        "unit": "n.a."
                    },
                    "neuropil": {
                        "name": "Neuropil",
                        "description": "Neuropil fluorescence",
                        "unit": "n.a."
                    },
                    "deconvolved": {
                        "name": "Deconvolved",
                        "description": "Deconvolved activity",
                        "unit": "n.a."
                    }
                }
            },

            "DfOverF": {
                "name": "DfOverF",
                "suite2p_analysis": {
                    "dff": {
                        "name": "DfOverF",
                        "description": "Delta F over F",
                        "unit": "n.a."
                    }
                }
            },

            "SegmentationImages": {
                "name": "SegmentationImages",
                "description": "Summary images from segmentation",
                "suite2p_analysis": {
                    "correlation": {
                        "name": "correlation_image",
                        "description": "Correlation image from Suite2p"
                    },
                    "mean": {
                        "name": "mean_image",
                        "description": "Mean image from Suite2p"
                    }
                }
            }
        }
    }


The metadata_key Parameter
--------------------------

All imaging and segmentation interfaces accept a ``metadata_key`` parameter. This parameter is
**keyword-only** to ensure explicit usage.

.. code-block:: python

    class BaseImagingExtractorInterface(BaseExtractorInterface):
        def __init__(
            self,
            *,  # Force keyword-only
            verbose: bool = False,
            photon_series_type: Literal["OnePhotonSeries", "TwoPhotonSeries"] = "TwoPhotonSeries",
            metadata_key: str = "default",
            **source_data,
        ):
            self.metadata_key = metadata_key
            ...

Key Propagation
~~~~~~~~~~~~~~~

The ``metadata_key`` propagates to all components created by an interface:

- ``metadata["Devices"][metadata_key]`` - The imaging device
- ``metadata["Ophys"]["ImagingPlanes"][metadata_key]`` - The imaging plane
- ``metadata["Ophys"]["TwoPhotonSeries"][metadata_key]`` - The photon series (if TwoPhotonSeries)
- ``metadata["Ophys"]["OnePhotonSeries"][metadata_key]`` - The photon series (if OnePhotonSeries)

For segmentation interfaces:

- ``metadata["Ophys"]["ImageSegmentation"][metadata_key]`` - The plane segmentation
- ``metadata["Ophys"]["Fluorescence"][metadata_key]`` - The fluorescence traces
- ``metadata["Ophys"]["DfOverF"][metadata_key]`` - The DfOverF traces
- ``metadata["Ophys"]["SegmentationImages"][metadata_key]`` - Summary images


Linking Imaging Planes and Devices in Ophys
--------------------------------------------

In NWB, some components are fully contained within their parent while others exist as separate,
linked objects. This distinction affects how they are represented in metadata:

**Contained components** like ``optical_channel`` are fully specified as nested metadata inside
their parent. An ImagingPlane's optical channels are defined directly within the ImagingPlane
metadata dictionary because they exist only within that ImagingPlane.

**Linked components** like Device and ImagingPlane are separate NWB objects that can be shared
or referenced by multiple other objects. For example, an ImagingPlane must reference the Device
(microscope) that was used to acquire the data, and a TwoPhotonSeries must reference the ImagingPlane
where the imaging occurred.

At metadata time, we don't have actual NWB objects yet - we only have dictionaries describing them.
To express these relationships between linked components, we use special ``_metadata_key`` fields
that contain the key of the referenced component. At NWB creation time, these string references
are resolved to actual NWB objects.

device_metadata_key
~~~~~~~~~~~~~~~~~~~

Used in ImagingPlane to reference its Device:

.. code-block:: python

    imaging_plane = {
        "name": "ImagingPlane",
        "device_metadata_key": "visual_cortex",  # Points to metadata["Devices"]["visual_cortex"]
        ...
    }

When the NWB file is created, the code looks up ``metadata["Devices"]["visual_cortex"]``,
creates the Device object, and links it to the ImagingPlane.

imaging_plane_metadata_key
~~~~~~~~~~~~~~~~~~~~~~~~~~

Used in PhotonSeries and PlaneSegmentation to reference their ImagingPlane:

.. code-block:: python

    photon_series = {
        "name": "TwoPhotonSeries",
        "imaging_plane_metadata_key": "visual_cortex",  # Points to ImagingPlanes["visual_cortex"]
        ...
    }

    plane_segmentation = {
        "name": "PlaneSegmentation",
        "imaging_plane_metadata_key": "visual_cortex",
        ...
    }

This allows multiple components (e.g., multiple segmentation pipelines) to reference the same
ImagingPlane, as shown in the how-to guide for annotating multiple segmentations of the same data.
