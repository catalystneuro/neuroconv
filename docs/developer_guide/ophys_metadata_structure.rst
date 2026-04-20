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

            "MicroscopySeries": {
                "visual_cortex": {
                    "name": "TwoPhotonSeriesVisualCortex",
                    "description": "Two-photon calcium imaging",
                    "imaging_plane_metadata_key": "visual_cortex",  # Reference to imaging plane
                    "unit": "n.a.",
                    "dimension": [512, 512]
                },
                "hippocampus": {
                    "name": "OnePhotonSeriesHippocampus",
                    "description": "Miniscope calcium imaging",
                    "imaging_plane_metadata_key": "hippocampus",
                    "unit": "n.a.",
                    "dimension": [480, 752]
                }
            },

            "PlaneSegmentations": {
                "suite2p_analysis": {
                    "name": "PlaneSegmentation",
                    "description": "ROIs detected by Suite2p",
                    "imaging_plane_metadata_key": "visual_cortex"
                }
            },

            "RoiResponses": {
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
                    },
                    "denoised": {
                        "name": "Denoised",
                        "description": "Denoised activity",
                        "unit": "n.a."
                    },
                    "baseline": {
                        "name": "Baseline",
                        "description": "Baseline fluorescence",
                        "unit": "n.a."
                    },
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

    class SomeOphysInterface(BaseDataInterface):
        def __init__(
            self,
            *,  # Force keyword-only
            verbose: bool = False,
            metadata_key: Optional[str] = None,
            **source_data,
        ):
            self.metadata_key = metadata_key
            ...

The argument name ``metadata_key`` is the same across all interfaces ensuring a common API.
When ``None`` (the default), the interface automatically generates a unique key from the
parameters that make the interface unique (e.g. stream name, channel name). When the user
passes an explicit value, they take responsibility for uniqueness and can use it to
intentionally share or customize metadata keys.

The default is ``None`` rather than a hardcoded string (e.g. ``"caiman_segmentation"``) for
consistency across interfaces. Multi-stream and multi-channel interfaces (like
``ScanImageImagingInterface``) cannot have a fixed default because the key must include
runtime parameters such as ``channel_name`` and ``plane_index``. Using ``None`` as the sentinel
and resolving the default in ``__init__`` lets every interface share the same pattern:
simple interfaces pick a static string, and parametric interfaces build the key from their
constructor arguments.

Key Propagation
~~~~~~~~~~~~~~~

The ``metadata_key`` parameter determines the entry point for the interface's **primary object(s)**.
For imaging interfaces, this is the MicroscopySeries; for segmentation interfaces, this is the
PlaneSegmentation and RoiResponses. Linked objects (ImagingPlane, Device) are resolved through
their own ``_metadata_key`` references, which may point to different entries.

For an imaging interface with ``metadata_key="visual_cortex"``:

- ``metadata["Ophys"]["MicroscopySeries"]["visual_cortex"]`` - The primary object (direct lookup via ``metadata_key``)
- ``metadata["Ophys"]["ImagingPlanes"][imaging_plane_metadata_key]`` - Resolved via ``imaging_plane_metadata_key`` inside the MicroscopySeries entry
- ``metadata["Devices"][device_metadata_key]`` - Resolved via ``device_metadata_key`` inside the ImagingPlane entry

For a segmentation interface with ``metadata_key="suite2p_analysis"``:

- ``metadata["Ophys"]["PlaneSegmentations"]["suite2p_analysis"]`` - Direct lookup via ``metadata_key``
- ``metadata["Ophys"]["RoiResponses"]["suite2p_analysis"]`` - Direct lookup via the same ``metadata_key``
- ``metadata["Ophys"]["ImagingPlanes"][imaging_plane_metadata_key]`` - Resolved via ``imaging_plane_metadata_key`` inside the PlaneSegmentation entry
- ``metadata["Devices"][device_metadata_key]`` - Resolved via ``device_metadata_key`` inside the ImagingPlane entry
- ``metadata["Ophys"]["SegmentationImages"]["suite2p_analysis"]`` - Summary images

In the simplest case, all these keys happen to be the same value (the interface's ``metadata_key``),
which is what ``get_metadata()`` produces by default. But the indirection through ``_metadata_key``
fields allows different components to reference shared resources. For example, two segmentation
pipelines can point their ``imaging_plane_metadata_key`` to the same ImagingPlane entry, and two
imaging planes can point their ``device_metadata_key`` to the same Device entry.


Single ImageSegmentation Container
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

While having multiple PlaneSegmentations makes sense (different segmentation algorithms like Suite2p
vs CaImAn, or multiple runs of the same algorithm), there is no clear use case for multiple
ImageSegmentation containers in an NWB file.

PyNWB and the NWB schema allow multiple ImageSegmentation containers, but NeuroConv does not support
this. Instead, NeuroConv uses a single, non-editable ImageSegmentation container where all
PlaneSegmentations are stored. This is handled internally and users cannot configure the
ImageSegmentation container. Users work directly with ``PlaneSegmentations`` in metadata, and
NeuroConv places them in the single ImageSegmentation container when creating the NWB file.

This simplifies both the metadata specification (no need to manage container names) and the
organization of the resulting NWB file.


Unified MicroscopySeries
~~~~~~~~~~~~~~~~~~~~~~~~

Metadata uses a unified ``MicroscopySeries`` key for all imaging data, regardless of whether
it will be written as ``TwoPhotonSeries`` or ``OnePhotonSeries`` in the NWB file.

The choice of NWB neurodata type (``TwoPhotonSeries`` vs ``OnePhotonSeries``) is specified as a
**conversion option**, not in metadata. This follows the provenance principle: metadata describes
the data, while conversion options determine how to write it to NWB.

For format-specific interfaces (e.g., ScanImageImagingInterface), the series type is extracted
from the source data. For generic interfaces (e.g., TiffImagingInterface), users must specify
the series type at conversion time:

.. code-block:: python

    # Format-specific interface - series type extracted from source
    interface = ScanImageImagingInterface(file_path="data.tif", metadata_key="visual_cortex")
    interface.add_to_nwbfile(nwbfile, metadata)  # Uses extracted type (TwoPhotonSeries)

    # Generic interface - series type must be specified
    interface = TiffImagingInterface(file_path="data.tif", metadata_key="visual_cortex")
    interface.add_to_nwbfile(nwbfile, metadata, photon_series_type="TwoPhotonSeries")

    # Override is always possible
    interface.add_to_nwbfile(nwbfile, metadata, photon_series_type="OnePhotonSeries")


Unified RoiResponses
~~~~~~~~~~~~~~~~~~~~

All ROI trace types (raw fluorescence, neuropil, deconvolved, denoised, baseline, df/f) are
stored under a single ``RoiResponses`` key in metadata. This consolidates what NWB core splits
into separate ``Fluorescence`` and ``DfOverF`` containers.

At write time, all traces are written as ``RoiResponseSeries`` inside a single ``Fluorescence``
container, without splitting into ``Fluorescence`` and ``DfOverF``. This follows the direction
of `nwb-schema#616 <https://github.com/NeurodataWithoutBorders/nwb-schema/issues/616>`_ and
matches ndx-microscopy's single-container pattern (``MicroscopyResponseSeriesContainer``).


Alignment with ndx-microscopy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The metadata structure is designed to align with the `ndx-microscopy <https://github.com/catalystneuro/ndx-microscopy>`_
extension, which represents the future direction of optical physiology in NWB.

ndx-microscopy uses:

- ``MicroscopySeries`` for all imaging data (instead of separate ``TwoPhotonSeries``/``OnePhotonSeries``)
- ``MicroscopyResponseSeries`` for all ROI traces (instead of separate ``Fluorescence``/``DfOverF``)

By adopting similar patterns (``MicroscopySeries``, ``RoiResponses``), NeuroConv's metadata
structure will require minimal changes when ndx-microscopy is integrated into NWB core.
This makes the eventual transition smoother for users.


Linking and Object Creation
---------------------------

Each interface's goal is to create its **primary object(s)** in NWB. For example, an imaging interface creates
a MicroscopySeries (e.g. TwoPhotonSeries, OnePhotonSeries). The metadata specifies attributes
of that object (name, description, unit, etc.) but also its linked objects: an ImagingPlane for
the series, and in turn a Device for the ImagingPlane.

Contained vs Linked Components
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In NWB, some components are fully contained within their parent while others exist as separate,
linked objects. This distinction affects how they are represented in metadata:

**Contained components** like ``optical_channel`` are fully specified as nested metadata inside
their parent. An ImagingPlane's optical channels are defined directly within the ImagingPlane
metadata dictionary because they exist only within that ImagingPlane.

**Linked components** like Device and ImagingPlane are separate NWB objects that can be shared
or referenced by multiple other objects. For example, an ImagingPlane must reference the Device
(microscope) that was used to acquire the data, and a TwoPhotonSeries must reference the ImagingPlane
where the imaging occurred.

How Linking Works
~~~~~~~~~~~~~~~~~

In the metadata dict, we don't have actual NWB objects yet, only dictionaries describing them.
To express relationships between linked components, we use special ``_metadata_key`` fields
that contain the key of the referenced component.

``device_metadata_key`` is used in ImagingPlane to reference its Device:

.. code-block:: python

    imaging_plane = {
        "name": "ImagingPlane",
        "device_metadata_key": "visual_cortex",  # Points to metadata["Devices"]["visual_cortex"]
        ...
    }

``imaging_plane_metadata_key`` is used in PhotonSeries and PlaneSegmentation to reference their
ImagingPlane:

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

When Objects Are Created
~~~~~~~~~~~~~~~~~~~~~~~~

Linked objects (Devices, ImagingPlanes, etc.) are not created when the metadata dict is assembled.
They are created when ``add_to_nwbfile`` is called. The metadata dict defines what *could* be
created, and the ``_metadata_key`` references determine what actually gets written to the NWB file.
At that point, the string references are resolved to actual NWB objects.

The rules are:

1. Only entries that are actually referenced by other objects (via ``_metadata_key`` fields) are
   created. Entries that exist in the metadata dict but are not referenced by anything will not be
   written to the file. This means you can define all the devices of a conversion in a shared YAML
   and only the ones that are actually linked will end up in the NWB file.

2. If a required link is missing (e.g. an ImagingPlane has no ``device_metadata_key``) and the
   object requires a linked object (e.g. an ImagingPlane requires a Device), a default object
   will be created and linked automatically at writing time.

3. For shared resources (e.g. two imaging planes using the same microscope), the user or the
   converter sets the ``_metadata_key`` references explicitly. The object is created by whichever
   interface writes first, and subsequent interfaces reuse the existing object.

.. code-block:: python

    # Two imaging planes sharing one device
    metadata["Devices"]["shared_microscope"] = {
        "name": "Microscope",
        "description": "Two-photon microscope used for both planes",
        "manufacturer": "Thorlabs",
    }

    metadata["Ophys"]["ImagingPlanes"]["plane_area1"] = {
        "name": "ImagingPlaneArea1",
        "location": "V1",
        "device_metadata_key": "shared_microscope",
    }

    metadata["Ophys"]["ImagingPlanes"]["plane_area2"] = {
        "name": "ImagingPlaneArea2",
        "location": "V2",
        "device_metadata_key": "shared_microscope",
    }

Note that device keys (and imaging plane keys) are independent of any interface's ``metadata_key``.
They can be any arbitrary string, as shown by ``"shared_microscope"`` above, which does not
correspond to any interface's key. No interface "owns" the device; it is created at write time by
whichever interface first follows the reference chain to it.

Because only referenced entries are written to the NWB file, the metadata dict can hold all
possible components (e.g. in a shared YAML) and the ``_metadata_key`` links control which ones
are actually used for each conversion. This enables a workflow where a single YAML file contains
the full metadata for a project (all devices, imaging planes, etc.) and is shared across sessions
in a multi-session conversion script. For each session, the conversion code sets the
``_metadata_key`` references programmatically to select which components to write and how to link
them. For example, different sessions might link their imaging planes to different devices, or
different segmentation runs might reference different imaging planes, all from the same shared
metadata file.
