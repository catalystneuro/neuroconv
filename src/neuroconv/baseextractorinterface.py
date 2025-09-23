"""Abstract class defining the structure of all Extractor-based Interfaces."""

import warnings
from abc import ABC

from .basetemporalalignmentinterface import BaseTemporalAlignmentInterface


class BaseExtractorInterface(BaseTemporalAlignmentInterface, ABC):
    """
    Abstract class defining the structure of all Extractor-based Interfaces.
    """

    def __init__(self, **source_data):
        super().__init__(**source_data)
        self._extractor_instance = self._initialize_extractor(source_data)
        self._extractor_class = self._extractor_instance.__class__
        self.extractor_kwargs = source_data

    def _initialize_extractor(self, source_data: dict):
        """
        Initialize and return the extractor instance for this interface.

        This method must be implemented by each concrete interface to specify
        which extractor to use and how to configure it.

        Parameters
        ----------
        source_data : dict
            The source data parameters passed to the interface constructor.

        Returns
        -------
        extractor_instance
            An initialized extractor instance.
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement _initialize_extractor method")

    @property
    def extractor(self):
        """
        Get the extractor class for this interface.

        .. deprecated:: 0.8.2
            The `extractor` attribute is deprecated and will be removed on or after March 2026.
            This attribute was confusingly named as it returns a class, not an instance.
            Use `_extractor_class` (private) or access the instance directly via `_extractor_instance`.

        Returns
        -------
        type
            The extractor class.
        """
        warnings.warn(
            "The 'extractor' attribute is deprecated and will be removed on or after March 2026. "
            "This attribute was confusingly named as it returns a class, not an instance.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._extractor_class

    def get_extractor(self):
        """
        Get the extractor class for this interface.

        .. deprecated:: 0.8.2
            The `get_extractor()` method is deprecated and will be removed on or after March 2026.
            This method was confusingly named as it returns a class, not an instance.
            Use `_extractor_class` (private) or access the instance directly via `_extractor_instance`.

        Returns
        -------
        type
            The extractor class.
        """
        warnings.warn(
            "The 'get_extractor()' method is deprecated and will be removed on or after March 2026. "
            "This method was confusingly named as it returns a class, not an instance.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._extractor_class
