"""Abstract class defining the structure of all Extractor-based Interfaces."""

from abc import ABC
from typing import Optional

from .basetemporalalignmentinterface import BaseTemporalAlignmentInterface
from .tools import get_package


class BaseExtractorInterface(BaseTemporalAlignmentInterface, ABC):
    """
    Abstract class defining the structure of all Extractor-based Interfaces.
    """

    # Manually override any of these attributes in a subclass if needed.
    # Note that values set at the level of class definition are called upon import.
    ExtractorModuleName: Optional[str] = None
    ExtractorName: Optional[str] = None  # Defaults to __name__.replace("Interface", "Extractor").
    Extractor = None  # Class loads dynamically on first call to .get_extractor()

    @classmethod
    def get_extractor(cls):
        if cls.Extractor is not None:
            return cls.Extractor
        extractor_module = get_package(package_name=cls.ExtractorModuleName)
        extractor = getattr(
            extractor_module,
            cls.ExtractorName or cls.__name__.replace("Interface", "Extractor"),
        )
        cls.Extractor = extractor
        return extractor
