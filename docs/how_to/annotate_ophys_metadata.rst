How to Annotate Optical Physiology Metadata
============================================

This guide demonstrates how to use the new dictionary-based metadata structure for optical physiology (ophys) interfaces in NeuroConv.

Background
----------

NeuroConv has transitioned from a list-based to a dictionary-based metadata structure for ophys components. This change provides:

- **Meaningful access**: Use descriptive keys instead of numeric indices
- **Better scalability**: Easily support multiple devices, imaging planes, and series
- **Improved clarity**: Clear relationships between components
- **Single key simplicity**: One metadata key per interface manages all components

Basic Usage with Single Interface
---------------------------------

Each ophys interface now accepts a ``metadata_key`` parameter that organizes all its components:

.. code-block:: python

    from neuroconv.datainterfaces import ScanImageImagingInterface

    # Create interface with a descriptive metadata key
    interface = ScanImageImagingInterface(
        file_path="path/to/data.tif",
        metadata_key="visual_cortex"  # This key will be used for all components
    )

    # Get metadata - notice the dictionary structure
    metadata = interface.get_metadata()

    # Access metadata using the key
    print(metadata["Devices"]["visual_cortex"])
    # {'name': 'Microscope', 'description': 'Two-photon microscope'}

    print(metadata["Ophys"]["ImagingPlanes"]["visual_cortex"])
    # {'name': 'ImagingPlane', 'device': 'visual_cortex', ...}

    print(metadata["Ophys"]["TwoPhotonSeries"]["visual_cortex"])
    # {'name': 'TwoPhotonSeries', 'imaging_plane': 'visual_cortex', ...}

Multi-Region Experiment Example
-------------------------------

This example shows how to combine data from multiple brain regions, each with its own imaging and segmentation:

.. code-block:: python

    from neuroconv import NWBConverter
    from neuroconv.datainterfaces import (
        ScanImageImagingInterface,
        Suite2pSegmentationInterface,
        MiniscopeImagingInterface,
        CaimanSegmentationInterface
    )

    # Step 1: Initialize interfaces with descriptive metadata keys

    # Visual cortex imaging and segmentation
    visual_imaging = ScanImageImagingInterface(
        file_path="data/visual_cortex.tif",
        metadata_key="visual_cortex"
    )

    visual_segmentation = Suite2pSegmentationInterface(
        folder_path="data/suite2p/visual_cortex",
        metadata_key="visual_cortex_suite2p"
    )

    # Hippocampus imaging and segmentation
    hippocampus_imaging = MiniscopeImagingInterface(
        folder_path="data/miniscope/hippocampus",
        metadata_key="hippocampus"
    )

    hippocampus_segmentation = CaimanSegmentationInterface(
        file_path="data/caiman/hippocampus_results.hdf5",
        metadata_key="hippocampus_caiman"
    )

    # Step 2: Create converter with all interfaces
    converter = NWBConverter({
        "visual_imaging": visual_imaging,
        "visual_segmentation": visual_segmentation,
        "hippocampus_imaging": hippocampus_imaging,
        "hippocampus_segmentation": hippocampus_segmentation
    })

    # Step 3: Get combined metadata
    metadata = converter.get_metadata()

    # The metadata structure now looks like:
    # {
    #     "Devices": {
    #         "visual_cortex": {...},
    #         "hippocampus": {...}
    #     },
    #     "Ophys": {
    #         "ImagingPlanes": {
    #             "visual_cortex": {...},
    #             "hippocampus": {...}
    #         },
    #         "TwoPhotonSeries": {
    #             "visual_cortex": {...}
    #         },
    #         "OnePhotonSeries": {
    #             "hippocampus": {...}
    #         },
    #         "ImageSegmentation": {
    #             "visual_cortex_suite2p": {...},
    #             "hippocampus_caiman": {...}
    #         }
    #     }
    # }

Editing Metadata
----------------

The dictionary structure makes it easy to edit metadata for specific components:

.. code-block:: python

    # Update device information
    metadata["Devices"]["visual_cortex"]["description"] = "Resonant scanning two-photon microscope"
    metadata["Devices"]["visual_cortex"]["manufacturer"] = "Thorlabs"

    metadata["Devices"]["hippocampus"]["description"] = "UCLA Miniscope v4"
    metadata["Devices"]["hippocampus"]["manufacturer"] = "Open Ephys"

    # Update imaging plane details
    metadata["Ophys"]["ImagingPlanes"]["visual_cortex"].update({
        "indicator": "GCaMP6s",
        "location": "V1 layer 2/3",
        "excitation_lambda": 920.0,
        "imaging_rate": 30.0
    })

    metadata["Ophys"]["ImagingPlanes"]["hippocampus"].update({
        "indicator": "GCaMP6f",
        "location": "CA1 pyramidal layer",
        "excitation_lambda": 470.0,
        "imaging_rate": 25.0
    })

    # Update series descriptions
    metadata["Ophys"]["TwoPhotonSeries"]["visual_cortex"]["description"] = (
        "Calcium imaging during visual stimulation paradigm"
    )

    metadata["Ophys"]["OnePhotonSeries"]["hippocampus"]["description"] = (
        "Calcium imaging during spatial navigation task"
    )

    # Update segmentation descriptions
    metadata["Ophys"]["ImageSegmentation"]["visual_cortex_suite2p"]["description"] = (
        "ROI segmentation of visual cortex neurons responding to oriented gratings"
    )

    metadata["Ophys"]["ImageSegmentation"]["hippocampus_caiman"]["description"] = (
        "ROI segmentation of hippocampal place cells"
    )

Running the Conversion
----------------------

After editing metadata, run the conversion:

.. code-block:: python

    # Convert to NWB with edited metadata
    converter.run_conversion(
        nwbfile_path="multi_region_ophys_experiment.nwb",
        metadata=metadata,
        overwrite=True
    )

Best Practices for Metadata Keys
---------------------------------

Choose descriptive metadata keys that clearly identify the data:

**Good examples:**

- ``"visual_cortex"`` - Clear anatomical location
- ``"visual_cortex_suite2p"`` - Location + analysis method
- ``"hippocampus_ca1"`` - Specific subregion
- ``"m1_layer5"`` - Brain region + layer
- ``"gcamp6s_920nm"`` - Indicator + wavelength

**Avoid:**

- ``"data1"``, ``"data2"`` - Not descriptive
- ``"default"`` - Only use when you have a single data stream
- Very long keys that are hard to type

Backward Compatibility
----------------------

The new structure maintains backward compatibility. If you have existing code using the old list-based structure, it will be automatically converted with a deprecation warning:

.. code-block:: python

    # Old structure (still works but deprecated)
    old_metadata = {
        "Ophys": {
            "ImagingPlane": [{"name": "ImagingPlane", ...}],  # List
            "TwoPhotonSeries": [{"name": "TwoPhotonSeries", ...}]  # List
        }
    }

    # Will be automatically converted to new structure with warning

Advanced Usage: Multi-Channel Imaging
-------------------------------------

For experiments with multiple channels from the same location:

.. code-block:: python

    # Multiple channels from the same brain region
    green_channel = ScanImageImagingInterface(
        file_path="data/green_channel.tif",
        channel_name="Green",
        metadata_key="cortex_green"
    )

    red_channel = ScanImageImagingInterface(
        file_path="data/red_channel.tif",
        channel_name="Red",
        metadata_key="cortex_red"
    )

    converter = NWBConverter({
        "green": green_channel,
        "red": red_channel
    })

    metadata = converter.get_metadata()

    # Customize metadata for each channel
    metadata["Ophys"]["ImagingPlanes"]["cortex_green"]["optical_channel"][0].update({
        "name": "GreenChannel",
        "emission_lambda": 525.0
    })

    metadata["Ophys"]["ImagingPlanes"]["cortex_red"]["optical_channel"][0].update({
        "name": "RedChannel",
        "emission_lambda": 600.0
    })

Summary
-------

The dictionary-based metadata structure provides a more intuitive and scalable way to work with ophys data in NeuroConv:

1. **Use meaningful keys**: Choose descriptive ``metadata_key`` values
2. **Access by key**: Use dictionary syntax instead of list indices
3. **One key per interface**: Each interface's key manages all its components
4. **Easy editing**: Directly update specific components by their keys
5. **Automatic relationships**: Components reference each other by metadata keys

This structure makes it easier to work with complex experiments involving multiple brain regions, imaging modalities, and analysis pipelines.
