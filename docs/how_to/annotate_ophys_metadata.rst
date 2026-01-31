.. _annotate_ophys_metadata:

How to Annotate Optical Physiology Data
=======================================

This guide provides instructions for annotating optical physiology (ophys) data using NeuroConv.

Optical physiology metadata in NWB files includes information about the imaging device (microscope),
imaging planes (where and how the imaging was performed), microscopy series (the actual imaging data),
and segmentation results (ROIs and response traces).


How to Annotate a Single Data Interface
---------------------------------------

Each imaging interface uses a ``metadata_key`` parameter that organizes all related metadata components.
The same key is used to access the ImagingPlane, MicroscopySeries, and Device - keeping them linked together.

.. code-block:: python

    from neuroconv.datainterfaces import TiffImagingInterface

    # Define a metadata_key that will link all components together
    metadata_key = "visual_cortex"

    # Create an interface with the metadata_key
    interface = TiffImagingInterface(
        file_path="path/to/imaging_data.tif",
        sampling_frequency=30.0,
        metadata_key=metadata_key,
    )

    metadata = interface.get_metadata()

    # The same metadata_key is used to access all related components:
    # - metadata["Devices"][metadata_key] -> the imaging device
    # - metadata["Ophys"]["ImagingPlanes"][metadata_key] -> the imaging plane
    # - metadata["Ophys"]["MicroscopySeries"][metadata_key] -> the microscopy series

    # Annotate the imaging plane
    imaging_plane = metadata["Ophys"]["ImagingPlanes"][metadata_key]
    imaging_plane["name"] = "ImagingPlaneVisualCortex"
    imaging_plane["description"] = "Imaging plane in V1 layer 2/3"
    imaging_plane["indicator"] = "GCaMP6s"
    imaging_plane["location"] = "V1 layer 2/3"
    imaging_plane["excitation_lambda"] = 920.0
    imaging_plane["optical_channel"][0]["emission_lambda"] = 510.0

    # Annotate the microscopy series
    microscopy_series = metadata["Ophys"]["MicroscopySeries"][metadata_key]
    microscopy_series["name"] = "TwoPhotonSeriesVisualCortex"
    microscopy_series["description"] = "Calcium imaging during visual stimulation"

    # Annotate the device
    device = metadata["Devices"][metadata_key]
    device["name"] = "Microscope"
    device["description"] = "Custom two-photon microscope, data acquired with ScanImage (VIDRIO)"
    device["manufacturer"] = "DIY"

    # Convert to NWB - specify the series type (TwoPhotonSeries or OnePhotonSeries)
    nwbfile = interface.create_nwbfile(
        metadata=metadata,
        photon_series_type="TwoPhotonSeries",  # Choose the NWB neurodata type
    )


How to Annotate Multi-Plane Imaging Data
-----------------------------------------

When you have imaging data from multiple planes (e.g., imaging different cortical layers), use a different
``metadata_key`` for each plane. This creates separate, properly linked components for each imaging plane.

.. code-block:: python

    from neuroconv.datainterfaces import TiffImagingInterface
    from neuroconv import NWBConverter

    # Create an interface for each cortical layer with its own metadata_key
    layer2_3 = TiffImagingInterface(
        file_path="path/to/layer2_3.tif",
        sampling_frequency=30.0,
        metadata_key="layer2_3",
    )

    layer4 = TiffImagingInterface(
        file_path="path/to/layer4.tif",
        sampling_frequency=30.0,
        metadata_key="layer4",
    )

    layer5 = TiffImagingInterface(
        file_path="path/to/layer5.tif",
        sampling_frequency=30.0,
        metadata_key="layer5",
    )

    # Combine all planes in a converter
    converter = NWBConverter(
        data_interfaces={
            "layer2_3": layer2_3,
            "layer4": layer4,
            "layer5": layer5,
        }
    )

    metadata = converter.get_metadata()

    # Annotate each plane with its cortical layer information
    metadata["Ophys"]["ImagingPlanes"]["layer2_3"]["name"] = "ImagingPlaneLayer2_3"
    metadata["Ophys"]["ImagingPlanes"]["layer2_3"]["description"] = "V1 layer 2/3 at 150um depth"
    metadata["Ophys"]["ImagingPlanes"]["layer4"]["name"] = "ImagingPlaneLayer4"
    metadata["Ophys"]["ImagingPlanes"]["layer4"]["description"] = "V1 layer 4 at 350um depth"
    metadata["Ophys"]["ImagingPlanes"]["layer5"]["name"] = "ImagingPlaneLayer5"
    metadata["Ophys"]["ImagingPlanes"]["layer5"]["description"] = "V1 layer 5 at 500um depth"

    # Set common metadata across all planes
    for layer_key in ["layer2_3", "layer4", "layer5"]:
        metadata["Ophys"]["ImagingPlanes"][layer_key]["indicator"] = "GCaMP6s"
        metadata["Ophys"]["ImagingPlanes"][layer_key]["location"] = "Primary visual cortex"
        metadata["Ophys"]["ImagingPlanes"][layer_key]["excitation_lambda"] = 920.0

    # Specify photon_series_type in conversion_options for each interface
    converter.run_conversion(
        nwbfile_path="multiplane_imaging.nwb",
        metadata=metadata,
        conversion_options={
            "layer2_3": {"photon_series_type": "TwoPhotonSeries"},
            "layer4": {"photon_series_type": "TwoPhotonSeries"},
            "layer5": {"photon_series_type": "TwoPhotonSeries"},
        }
    )


How to Annotate Multiple Segmentations of the Same Data
-------------------------------------------------------

When you run multiple segmentation pipelines on the same imaging data (e.g., comparing Suite2p and CaImAn),
use a different ``metadata_key`` for each pipeline. Link them to the same imaging plane using
``imaging_plane_metadata_key`` to indicate they are segmenting the same data.

.. code-block:: python

    from neuroconv.datainterfaces import Suite2pSegmentationInterface, CaimanSegmentationInterface
    from neuroconv import NWBConverter

    # Each segmentation pipeline gets its own metadata_key
    suite2p_metadata_key = "suite2p"
    caiman_metadata_key = "caiman"

    suite2p_segmentation = Suite2pSegmentationInterface(
        folder_path="path/to/suite2p/plane0",
        metadata_key=suite2p_metadata_key,
    )

    caiman_segmentation = CaimanSegmentationInterface(
        file_path="path/to/caiman_results.hdf5",
        metadata_key=caiman_metadata_key,
    )

    converter = NWBConverter(
        data_interfaces={
            "suite2p_interface": suite2p_segmentation,
            "caiman_interface": caiman_segmentation,
        }
    )

    metadata = converter.get_metadata()

    # Define the imaging plane that both segmentations are derived from
    imaging_plane_metadata_key = "my_imaging_plane"
    metadata["Ophys"]["ImagingPlanes"][imaging_plane_metadata_key] = {
        "name": "ImagingPlane",
        "description": "Imaging plane in V1",
        "indicator": "GCaMP6s",
        "location": "V1 layer 2/3",
        "excitation_lambda": 920.0,
        "device_metadata_key": "my_device",
    }

    # Annotate each pipeline's segmentation
    metadata["Ophys"]["PlaneSegmentations"][suite2p_metadata_key]["name"] = "PlaneSegmentationSuite2p"
    metadata["Ophys"]["PlaneSegmentations"][suite2p_metadata_key]["description"] = "Suite2p ROI detection"
    metadata["Ophys"]["PlaneSegmentations"][caiman_metadata_key]["name"] = "PlaneSegmentationCaImAn"
    metadata["Ophys"]["PlaneSegmentations"][caiman_metadata_key]["description"] = "CaImAn CNMF-E ROI detection"

    # Link both segmentations to the same imaging plane
    metadata["Ophys"]["PlaneSegmentations"][suite2p_metadata_key]["imaging_plane_metadata_key"] = imaging_plane_metadata_key
    metadata["Ophys"]["PlaneSegmentations"][caiman_metadata_key]["imaging_plane_metadata_key"] = imaging_plane_metadata_key

    converter.run_conversion(
        nwbfile_path="multi_pipeline_segmentation.nwb",
        metadata=metadata,
    )


.. note::

    If you have a use case not covered here, please open an issue at
    `NeuroConv GitHub Issues <https://github.com/catalystneuro/neuroconv/issues>`_.
