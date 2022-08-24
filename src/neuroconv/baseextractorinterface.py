"""Abstract class defining the structure of all Extractor-based Interfaces."""
from typing import Optional

from .basedatainterface import BaseDataInterface
from .tools import get_package


class _LazyExtractorImport(type(BaseDataInterface), type):
    def __getattribute__(self, name):
        if name == "Extractor" and super().__getattribute__("Extractor") is None:
            extractor_module = get_package(package_name=super().__getattribute__("ExtractorModuleName"))
            extractor = getattr(
                extractor_module,
                super().__getattribute__("ExtractorName") or self.__name__.replace("Interface", "Extractor"),
            )
            return extractor
        return super().__getattribute__(name)


class BaseExtractorInterface(BaseDataInterface, metaclass=_LazyExtractorImport):
    """
    Abstract class defining the structure of all Extractor-based Interfaces.

    Harnesses an override of the class-level __getattribute__ to perform on-demand imports of the extractor class.
    Since the type of every class is itself a 'type' (a builtin object), direct overrides are not possible.
    Hence we use a metaclass whose parent is 'type' to act as an intermediary with the builtin.
    This metaclass also requires a mix-in with the parent ABC class since the ABCMeta causes conflicts otherwise.

    However, the __getattribute__ override is only a 'getter' with respect to the property; setting it in instances
    of the class is performed by a slight injection into the __new__ of the base class.
    """

    # Manually override any of these attributes in a subclass if needed.
    # Note that values set at the level of class definition are called upon import.
    ExtractorModuleName: Optional[str] = None
    ExtractorName: Optional[str] = None  # Defaults to __name__.replace("Interface", "Extractor").
    Extractor = None  # Loads dynamically on first access attempt

    def __new__(cls, *args, **kwargs):
        cls.Extractor = getattr(cls, "Extractor")
        return object.__new__(cls)
