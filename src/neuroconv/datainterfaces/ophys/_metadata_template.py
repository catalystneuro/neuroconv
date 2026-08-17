"""The blank structures the ophys metadata templates are built from.

An imaging interface writes a series through an imaging plane and a segmentation interface writes ROIs
on one, so both bases describe the same plane and the same microscope behind it. Those entries live
here rather than being written twice and drifting apart, as the schema definitions in
``_metadata_schema.py`` do.

Every field only the experimenter can supply is ``None``, which pynwb rejects for all of them, so a
template used as it is fails rather than writing a blank.
"""


def _get_device_template_entry(*, device_model_metadata_key: str) -> dict:
    """A blank microscope, the device an imaging plane links to.

    The make and catalog specification belong to the model rather than to the microscope: pynwb
    deprecated ``Device.manufacturer``, ``model_number`` and ``model_name`` in favor of a linked
    ``DeviceModel``, so those are offered there and only the serial number of this one instrument
    stays here.
    """
    return dict(
        name=None,
        description=None,
        serial_number=None,
        device_model_metadata_key=device_model_metadata_key,
    )


def _get_device_model_template_entry() -> dict:
    """A blank microscope model: the make and catalog specification, shared by every recording on it.

    Optional as a whole. To drop it, delete the entry and the ``device_model_metadata_key`` pointing
    at it.
    """
    return dict(name=None, manufacturer=None, model_number=None, description=None)


def _get_imaging_plane_template_entry(*, device_metadata_key: str) -> dict:
    """
    A blank imaging plane, already linked to the device this interface's objects hang off.

    ``excitation_lambda``, ``indicator`` and ``location`` are what NWB requires of a plane and what an
    imaging file rarely carries, so they are the blanks that matter. The rest are optional and appear
    so that a user knows the writer accepts them; delete the ones this recording cannot answer.
    """
    return dict(
        name=None,
        description=None,
        device_metadata_key=device_metadata_key,
        excitation_lambda=None,
        indicator=None,
        location=None,
        imaging_rate=None,
        optical_channel=[dict(name=None, description=None, emission_lambda=None)],
        # The units are stated rather than blanked: they are a convention of the format, not a fact
        # about the recording, and NWB stores these two quantities in meters by default.
        origin_coords=None,
        origin_coords_unit="meters",
        grid_spacing=None,
        grid_spacing_unit="meters",
        reference_frame=None,
    )


def _resolve_device_metadata_key(*, source_metadata: dict, metadata_key: str) -> str:
    """
    The key the template's device belongs under: the one the interface already uses, or a generic one.

    An interface that read its microscope out of the source names it, and the template has to fill that
    entry's blanks rather than offer a second entry beside it. A ``Devices`` entry nothing links to is
    dropped at write time, so an invented key's blanks would never be read and the user would be filling
    in a device that never reaches the file.
    """
    imaging_planes_metadata = source_metadata.get("Ophys", {}).get("ImagingPlanes", {})
    device_metadata_key = imaging_planes_metadata.get(metadata_key, {}).get("device_metadata_key")
    if device_metadata_key is not None:
        return device_metadata_key

    device_metadata_keys = list(source_metadata.get("Devices", {}))
    return device_metadata_keys[0] if device_metadata_keys else "microscope"
