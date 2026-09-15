Selecting ROIs for Conversion
==============================

By default, segmentation interfaces write all ROIs from the source data to the
NWB file. In some cases, for example after curating the segmentation output,
you may want to include only a subset of the ROIs in the source data. To support this, segmentation
interfaces accept the ``roi_ids_to_add`` parameter in ``add_to_nwbfile()``
(and ``create_nwbfile()``) to specify which ROIs to write.


Inspecting Available ROI IDs
-----------------------------

Before filtering, you can inspect the available ROI IDs using the ``roi_ids``
property on any segmentation interface:

.. code-block:: python

    from neuroconv.tools.testing.mock_interfaces import MockSegmentationInterface

    interface = MockSegmentationInterface(num_rois=20)

    # Inspect all available ROI IDs
    print("All ROI IDs:", interface.roi_ids)


Filtering ROIs During Conversion
---------------------------------

Pass the ``roi_ids_to_add`` parameter to ``create_nwbfile()`` or ``add_to_nwbfile()``
to include only a subset of ROIs:

.. code-block:: python

    from neuroconv.tools.testing.mock_interfaces import MockSegmentationInterface

    interface = MockSegmentationInterface(num_rois=20)

    # Convert with only specific ROIs
    nwbfile = interface.create_nwbfile(roi_ids_to_add=["roi_00", "roi_03", "roi_10"])

    # Verify only selected ROIs are in the file
    plane_segmentation = nwbfile.processing["ophys"]["ImageSegmentation"]["PlaneSegmentation"]
    print("Number of ROIs in NWB:", len(plane_segmentation))  # 3
