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
        """
        Get the extractor class for this interface.

        Returns
        -------
        class
            The extractor class that this interface is based on.
        """
        if cls.Extractor is not None:
            return cls.Extractor
        extractor_module = get_package(package_name=cls.ExtractorModuleName)
        extractor = getattr(
            extractor_module,
            cls.ExtractorName or cls.__name__.replace("Interface", "Extractor"),
        )
        cls.Extractor = extractor
        return extractor

    def __init__(self, **source_data):
        super().__init__(**source_data)
        self.extractor = self.get_extractor()
        self.extractor_kwargs = self._source_data_to_extractor_kwargs(source_data)
        self._extractor_instance = self.extractor(**self.extractor_kwargs)

    def _source_data_to_extractor_kwargs(self, source_data: dict) -> dict:
        """
        Map the source_data to kwargs required to initialize the Extractor.

        Parameters
        ----------
        source_data : dict
            The source data dictionary passed to the interface.

        Returns
        -------
        dict
            The keyword arguments dictionary to pass to the extractor.
        """
        return source_data
