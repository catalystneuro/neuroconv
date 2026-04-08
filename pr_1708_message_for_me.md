# Add metadata_key support to base and simple segmentation interfaces

The dict-based segmentation pipeline (PRs #1692 and #1695) already exists in `roiextractors.py`, but the interface layer had no way to activate it. This PR wires up that pipeline by adding `metadata_key` and `use_new_metadata_format` to the segmentation interfaces, following the same pattern established for imaging in PR #1694.

`BaseSegmentationExtractorInterface` gains a `metadata_key` parameter stored as `self.metadata_key`, and `get_metadata` gains a keyword-only `use_new_metadata_format: bool = False` flag. When `True`, `get_metadata` returns only what the source file natively provides (provenance-first), leaving structure to the pipeline. `add_to_nwbfile` forwards `self.metadata_key` to `add_segmentation_to_nwbfile`, which already dispatches to the dict-based path when the key is present.

This PR migrates the four structurally simple interfaces (`CaimanSegmentationInterface`, `CnmfeSegmentationInterface`, `ExtractSegmentationInterface`, `SimaSegmentationInterface`) and `MockSegmentationInterface`. The `SegmentationExtractorInterfaceTestMixin` gains the same `test_get_metadata` / `check_extracted_metadata` / `check_extracted_metadata_old_list_format` pattern as `ImagingExtractorInterfaceTestMixin`. Suite2p, Minian, and Inscopix segmentation interfaces will follow in stacked PRs.
