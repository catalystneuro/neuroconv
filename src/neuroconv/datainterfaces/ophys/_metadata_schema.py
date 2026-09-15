"""Schema definitions shared by the ophys metadata blocks.

The imaging and segmentation bases describe overlapping registries (both link an imaging plane, both are
keyed by ``metadata_key``), so the entry definitions live here rather than being written twice and drifting.

Entries are deliberately permissive. Each one is handed to a pynwb constructor, so it may carry any field
that constructor takes, and pinning the full field list here would reject valid metadata every time pynwb
grows an argument. What is pinned is the shape, that an entry is an object, plus the cross-reference fields
no hdmf class knows about.
"""


def _keyed_registry(entry_reference: str) -> dict:
    """A registry keyed by ``metadata_key``, whose values are entries of the referenced definition."""
    return dict(type="object", additionalProperties={"$ref": entry_reference})


def _get_ophys_registry_entry_definitions() -> dict:
    """Return the ``definitions`` block the ophys registries reference."""
    return dict(
        ImagingPlaneEntry=dict(
            type="object",
            additionalProperties=True,
            properties=dict(
                name=dict(type="string", pattern="^[^/]*$"),
                description=dict(type="string"),
                indicator=dict(type="string"),
                location=dict(type="string"),
                device_metadata_key=dict(
                    type="string",
                    description="Key of this plane's device in metadata['Devices'].",
                ),
                optical_channel=dict(
                    type="array",
                    items=dict(
                        type="object",
                        additionalProperties=True,
                        properties=dict(
                            name=dict(type="string", pattern="^[^/]*$"),
                            description=dict(type="string"),
                        ),
                    ),
                ),
            ),
        ),
        MicroscopySeriesEntry=dict(
            type="object",
            additionalProperties=True,
            properties=dict(
                name=dict(type="string", pattern="^[^/]*$"),
                description=dict(type="string"),
                unit=dict(type="string"),
                imaging_plane_metadata_key=dict(
                    type="string",
                    description="Key of this series' imaging plane in metadata['Ophys']['ImagingPlanes'].",
                ),
            ),
        ),
        PlaneSegmentationEntry=dict(
            type="object",
            additionalProperties=True,
            properties=dict(
                name=dict(type="string", pattern="^[^/]*$"),
                description=dict(type="string"),
                imaging_plane_metadata_key=dict(
                    type="string",
                    description="Key of this segmentation's imaging plane in metadata['Ophys']['ImagingPlanes'].",
                ),
            ),
        ),
        # Traces and summary images are keyed twice: by the plane segmentation they belong to, and then by
        # the trace or image within it.
        RoiResponsesEntry=dict(
            type="object",
            additionalProperties=dict(
                type="object",
                additionalProperties=True,
                properties=dict(
                    name=dict(type="string", pattern="^[^/]*$"),
                    description=dict(type="string"),
                    unit=dict(type="string"),
                ),
            ),
        ),
        SegmentationImagesEntry=dict(
            type="object",
            additionalProperties=dict(
                type="object",
                additionalProperties=True,
                properties=dict(
                    name=dict(type="string", pattern="^[^/]*$"),
                    description=dict(type="string"),
                ),
            ),
        ),
    )
