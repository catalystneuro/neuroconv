"""Lazy type resolution for the top-level ``Devices`` / ``DeviceModels`` metadata registries.

A device (or device model) metadata entry may carry an optional ``type`` field naming the concrete
NWB class to build. The class is resolved on demand by importing its extension via
:func:`~neuroconv.tools.importing.get_package`, so an optional extension is imported only when an
entry of that type is actually written. This keeps the metadata shape stable across modalities and
honors neuroconv's optional-dependency model (a pure-ecephys conversion never imports
``ndx-ophys-devices``, for example).

The base class (``Device`` or ``DeviceModel``, passed in by the caller) is returned directly when an
entry omits ``type``; only extension subclasses live in the source maps below and are routed through
``get_package``. Adding support for a new extension is one data line per class, not import wiring.
"""

from ..importing import get_package

#: Extension device-instance types (subclasses of ``pynwb.device.Device``) that may appear as the
#: ``type`` of a ``metadata["Devices"]`` entry, mapped to ``(module, installation instructions)``.
_DEVICE_TYPE_SOURCES: dict[str, tuple[str, str | None]] = {
    "OpticalFiber": ("ndx_ophys_devices", "pip install ndx-ophys-devices"),
    "ExcitationSource": ("ndx_ophys_devices", "pip install ndx-ophys-devices"),
    "Photodetector": ("ndx_ophys_devices", "pip install ndx-ophys-devices"),
    "BandOpticalFilter": ("ndx_ophys_devices", "pip install ndx-ophys-devices"),
    "EdgeOpticalFilter": ("ndx_ophys_devices", "pip install ndx-ophys-devices"),
    "DichroicMirror": ("ndx_ophys_devices", "pip install ndx-ophys-devices"),
}

#: Extension device-model types (subclasses of ``pynwb.device.DeviceModel``) that may appear as the
#: ``type`` of a ``metadata["DeviceModels"]`` entry, mapped to ``(module, installation instructions)``.
_DEVICE_MODEL_TYPE_SOURCES: dict[str, tuple[str, str | None]] = {
    "OpticalFiberModel": ("ndx_ophys_devices", "pip install ndx-ophys-devices"),
    "ExcitationSourceModel": ("ndx_ophys_devices", "pip install ndx-ophys-devices"),
    "PhotodetectorModel": ("ndx_ophys_devices", "pip install ndx-ophys-devices"),
    "BandOpticalFilterModel": ("ndx_ophys_devices", "pip install ndx-ophys-devices"),
    "EdgeOpticalFilterModel": ("ndx_ophys_devices", "pip install ndx-ophys-devices"),
    "DichroicMirrorModel": ("ndx_ophys_devices", "pip install ndx-ophys-devices"),
}


def _resolve_type(type_name: str, *, sources: dict[str, tuple[str, str | None]], base_class: type) -> type:
    """Resolve a ``type`` string to its class, importing the providing extension on demand.

    The core base class (``base_class.__name__``) is returned directly. Any other ``type_name`` is
    looked up in ``sources`` and its extension imported via ``get_package``. Raises ``ValueError``
    for an unknown ``type_name`` and ``TypeError`` if the resolved class is not a subclass of
    ``base_class``.
    """
    if type_name == base_class.__name__:
        return base_class
    if type_name not in sources:
        known = [base_class.__name__, *sorted(sources)]
        raise ValueError(
            f"Unknown device type {type_name!r}. Known types: {known}. If this type comes from an "
            "NWB extension, add it to the device type source maps in "
            "neuroconv.tools.nwb_helpers._device_registry."
        )
    module_name, installation_instructions = sources[type_name]
    module = get_package(package_name=module_name, installation_instructions=installation_instructions)
    resolved_class = getattr(module, type_name)
    if not issubclass(resolved_class, base_class):
        raise TypeError(f"Resolved type {type_name!r} ({resolved_class}) is not a subclass of {base_class.__name__}.")
    return resolved_class
