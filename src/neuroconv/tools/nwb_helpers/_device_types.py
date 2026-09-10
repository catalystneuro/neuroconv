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

from hdmf.container import Container
from hdmf.utils import get_docval

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
    "Miniscope": ("ndx_miniscope", "pip install ndx-miniscope"),
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
            "neuroconv.tools.nwb_helpers._device_types."
        )
    module_name, installation_instructions = sources[type_name]
    module = get_package(package_name=module_name, installation_instructions=installation_instructions)
    resolved_class = getattr(module, type_name)
    if not issubclass(resolved_class, base_class):
        raise TypeError(f"Resolved type {type_name!r} ({resolved_class}) is not a subclass of {base_class.__name__}.")
    return resolved_class


#: Constructor arguments whose declared type is one of these are *links* to an object that lives
#: elsewhere in the file, not sub-objects to build inline. The metadata convention expresses a link
#: as a ``*_metadata_key`` resolved against the registry, never as an inline dict, so these are left
#: for the caller to resolve. ``ImagingPlane`` declares ``device -> Device``, which a naive
#: "the declared type is a Container, so build it" rule would otherwise try to construct inline.
_LINKED_CONTAINER_TYPE_NAMES = frozenset({"Device", "DeviceModel"})


def _get_inline_container_class(declared_type) -> tuple[type | None, bool]:
    """
    Resolve a docval ``type`` entry to the container class an inline metadata dict should build.

    Returns ``(None, False)`` when the argument is not an inline sub-object: a plain value, a link to
    an object stored elsewhere, or a type named by string (which cannot be constructed from here).
    The boolean reports whether the argument also accepts a list, as ``optical_channel`` does.
    """
    declared_types = declared_type if isinstance(declared_type, tuple) else (declared_type,)
    accepts_list = any(candidate in (list, tuple) for candidate in declared_types)

    for candidate in declared_types:
        # hdmf allows a type to be named by string; those are links in practice (``OpticalFiber``
        # declares ``model -> "DeviceModel"``) and cannot be resolved to a class from here anyway.
        if isinstance(candidate, str):
            continue
        if not isinstance(candidate, type) or not issubclass(candidate, Container):
            continue
        if candidate.__name__ in _LINKED_CONTAINER_TYPE_NAMES:
            return None, accepts_list
        return candidate, accepts_list

    return None, accepts_list


def _build_inline_containers(*, target_class: type, kwargs: dict) -> dict:
    """
    Build the inline sub-objects a container's constructor expects, in place of their metadata dicts.

    Metadata stays plain data all the way to construction: a sub-object is written inline as a dict
    (or a list of dicts), and is turned into the declared container class here, immediately before the
    parent is built. The target type is read off the parent's own constructor spec, so no field name
    or sub-object class is hardcoded. Values that are already container objects are left untouched,
    which is how a link resolved earlier by the caller passes through.
    """
    for argument in get_docval(target_class.__init__):
        argument_name = argument["name"]
        if argument_name not in kwargs:
            continue

        value = kwargs[argument_name]
        is_dict = isinstance(value, dict)
        is_list_of_dicts = isinstance(value, (list, tuple)) and len(value) > 0
        is_list_of_dicts = is_list_of_dicts and all(isinstance(element, dict) for element in value)
        if not (is_dict or is_list_of_dicts):
            continue

        container_class, accepts_list = _get_inline_container_class(argument["type"])
        if container_class is None:
            continue

        if is_dict:
            kwargs[argument_name] = container_class(**value)
        elif accepts_list:
            kwargs[argument_name] = [container_class(**element) for element in value]

    return kwargs
