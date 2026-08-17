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

    # Define a metadata_key for each cortical layer
    layer2_3_metadata_key = "layer2_3"
    layer4_metadata_key = "layer4"
    layer5_metadata_key = "layer5"

    # Create an interface for each cortical layer with its own metadata_key
    layer2_3_interface = TiffImagingInterface(
        file_path="path/to/layer2_3.tif",
        sampling_frequency=30.0,
        metadata_key=layer2_3_metadata_key,
    )

    layer4_interface = TiffImagingInterface(
        file_path="path/to/layer4.tif",
        sampling_frequency=30.0,
        metadata_key=layer4_metadata_key,
    )

    layer5_interface = TiffImagingInterface(
        file_path="path/to/layer5.tif",
        sampling_frequency=30.0,
        metadata_key=layer5_metadata_key,
    )

    # Combine all planes in a converter
    converter = NWBConverter(
        data_interfaces={
            "layer2_3_interface": layer2_3_interface,
            "layer4_interface": layer4_interface,
            "layer5_interface": layer5_interface,
        }
    )

    metadata = converter.get_metadata()

    # Annotate each plane with its cortical layer information
    metadata["Ophys"]["ImagingPlanes"][layer2_3_metadata_key]["name"] = "ImagingPlaneLayer2_3"
    metadata["Ophys"]["ImagingPlanes"][layer2_3_metadata_key]["description"] = "V1 layer 2/3 at 150um depth"
    metadata["Ophys"]["ImagingPlanes"][layer2_3_metadata_key]["location"] = "V1 layer 2/3"
    metadata["Ophys"]["ImagingPlanes"][layer4_metadata_key]["name"] = "ImagingPlaneLayer4"
    metadata["Ophys"]["ImagingPlanes"][layer4_metadata_key]["description"] = "V1 layer 4 at 350um depth"
    metadata["Ophys"]["ImagingPlanes"][layer4_metadata_key]["location"] = "V1 layer 4"
    metadata["Ophys"]["ImagingPlanes"][layer5_metadata_key]["name"] = "ImagingPlaneLayer5"
    metadata["Ophys"]["ImagingPlanes"][layer5_metadata_key]["description"] = "V1 layer 5 at 500um depth"
    metadata["Ophys"]["ImagingPlanes"][layer5_metadata_key]["location"] = "V1 layer 5"

    # Set common metadata across all planes
    for layer_key in [layer2_3_metadata_key, layer4_metadata_key, layer5_metadata_key]:
        metadata["Ophys"]["ImagingPlanes"][layer_key]["indicator"] = "GCaMP6s"
        metadata["Ophys"]["ImagingPlanes"][layer_key]["excitation_lambda"] = 920.0

    # Specify photon_series_type in conversion_options for each interface
    converter.run_conversion(
        nwbfile_path="multiplane_imaging.nwb",
        metadata=metadata,
        conversion_options={
            "layer2_3_interface": {"photon_series_type": "TwoPhotonSeries"},
            "layer4_interface": {"photon_series_type": "TwoPhotonSeries"},
            "layer5_interface": {"photon_series_type": "TwoPhotonSeries"},
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
    suite2p_metadata_key = "suite2p_metadata_key"
    caiman_metadata_key = "caiman_metadata_key"

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

    # Define the device used for imaging
    device_metadata_key = "my_device"
    metadata["Devices"][device_metadata_key] = {
        "name": "Microscope",
        "description": "Two-photon microscope",
        "manufacturer": "Thorlabs",
    }

    # Define the imaging plane that both segmentations are derived from
    imaging_plane_metadata_key = "my_imaging_plane"
    metadata["Ophys"]["ImagingPlanes"][imaging_plane_metadata_key] = {
        "name": "ImagingPlane",
        "description": "Imaging plane in V1",
        "indicator": "GCaMP6s",
        "location": "V1 layer 2/3",
        "excitation_lambda": 920.0,
        "device_metadata_key": device_metadata_key,
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


.. _how_to_annotate_ophys_from_a_template:

How to Annotate from a Template
-------------------------------

The sections above reach into ``get_metadata()`` and edit what it returns. That works, but it does not
tell you what is missing: ``get_metadata()`` reports what the source file recorded, so a field it leaves
out looks the same as a field that does not exist. ``get_metadata_template()`` answers the other
question. It returns those same source-derived values wrapped in the whole structure the writer expects,
with the cross-references already resolved and every field only you can answer set to ``None``:

.. code-block:: python

    from neuroconv.datainterfaces import TiffImagingInterface

    interface = TiffImagingInterface(
        file_path="path/to/imaging_data.tif",
        sampling_frequency=30.0,
        metadata_key="visual_cortex",
    )
    metadata = interface.get_metadata_template()

What comes back is printed in full, in both YAML and JSON, at
:ref:`Metadata Templates <ophys_metadata_template>`.

**The blanks are the checklist.** What comes back ``None`` is exactly what the source could not tell us,
and everything else is already done: the ``device_metadata_key`` that links the plane to the microscope
and the ``imaging_plane_metadata_key`` that links the series to the plane are wired for you. Fill in
what applies and delete what does not, since a blank left behind is refused at write time rather than
guessed at.

.. code-block:: python

    imaging_plane = metadata["Ophys"]["ImagingPlanes"]["visual_cortex"]
    imaging_plane["name"] = "ImagingPlaneVisualCortex"
    imaging_plane["description"] = "Imaging plane in V1 layer 2/3"
    imaging_plane["excitation_lambda"] = 920.0
    imaging_plane["indicator"] = "GCaMP6s"
    imaging_plane["location"] = "V1 layer 2/3"
    imaging_plane["imaging_rate"] = 30.0
    imaging_plane["optical_channel"][0].update(
        name="Green", description="Green channel", emission_lambda=510.0
    )

    microscopy_series = metadata["Ophys"]["MicroscopySeries"]["visual_cortex"]
    microscopy_series["name"] = "TwoPhotonSeriesVisualCortex"
    microscopy_series["description"] = "Calcium imaging during visual stimulation"
    microscopy_series["unit"] = "n.a."

    metadata["Devices"]["microscope"].update(
        name="Microscope",
        description="Custom two-photon microscope",
        serial_number="2019-04-01",
    )
    metadata["DeviceModels"]["microscope_model"].update(
        name="MicroscopeModel",
        manufacturer="DIY",
        description="Custom-built, no catalog model",
    )

    # This rig did not measure where the plane sat, and the scanner settings were not recorded.
    for unknown_field in ("origin_coords", "origin_coords_unit", "grid_spacing",
                          "grid_spacing_unit", "reference_frame"):
        del imaging_plane[unknown_field]
    for unknown_field in ("field_of_view", "pmt_gain", "scan_line_rate"):
        del microscopy_series[unknown_field]
    del metadata["DeviceModels"]["microscope_model"]["model_number"]

    nwbfile = interface.create_nwbfile(metadata=metadata)

A segmentation interface offers the same thing, sized to what its pipeline produced. Only the traces
and the summary images the file actually holds appear, so the entries you get back are the list to fill
in rather than a menu to check against your output:

.. code-block:: python

    from neuroconv.datainterfaces import Suite2pSegmentationInterface

    interface = Suite2pSegmentationInterface(
        folder_path="path/to/suite2p/plane0",
        metadata_key="suite2p",
    )
    metadata = interface.get_metadata_template()

    plane_segmentation = metadata["Ophys"]["PlaneSegmentations"]["suite2p"]
    plane_segmentation["name"] = "PlaneSegmentationSuite2p"
    plane_segmentation["description"] = "ROIs detected by Suite2p"

    # Whatever Suite2p wrote: raw and neuropil traces here, plus deconvolved and dff if it ran them.
    for trace_name, trace_metadata in metadata["Ophys"]["RoiResponses"]["suite2p"].items():
        trace_metadata["name"] = trace_name.capitalize()
        trace_metadata["description"] = f"Suite2p {trace_name} traces"
        trace_metadata["unit"] = "n.a."

    for image_name, image_metadata in metadata["Ophys"]["SegmentationImages"]["suite2p"].items():
        image_metadata["name"] = f"{image_name}_image"
        image_metadata["description"] = f"Suite2p {image_name} image"

The imaging plane and the device come back on the segmentation template too, and are filled in exactly
as above. If the same conversion also writes the imaging the pipeline ran on, do not fill them in twice:
point the segmentation's ``imaging_plane_metadata_key`` at the imaging interface's plane, as the
sections above do, and delete the plane the segmentation template offered.

.. note::

    If you have a use case not covered here, please open an issue at
    `NeuroConv GitHub Issues <https://github.com/catalystneuro/neuroconv/issues>`_.
