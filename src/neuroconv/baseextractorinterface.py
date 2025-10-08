"""Abstract class defining the structure of all Extractor-based Interfaces."""

import warnings
from abc import ABC, abstractmethod

from .basetemporalalignmentinterface import BaseTemporalAlignmentInterface


class BaseExtractorInterface(BaseTemporalAlignmentInterface, ABC):
    """
    Abstract class defining the structure of all Extractor-based Interfaces.
    """

    def __init__(self, **source_data):
        super().__init__(**source_data)
        self._extractor_instance = self._initialize_extractor(source_data)

    @classmethod
    @abstractmethod
    def get_extractor_class(cls):
        """
        Get the extractor class for this interface.

        This classmethod must be implemented by each concrete interface to specify
        which extractor class to use.

        Returns
        -------
        type or callable
            The extractor class or function to use for initialization.
        """
        pass

    def _initialize_extractor(self, interface_kwargs: dict):
        """
        Initialize and return the extractor instance for this interface.

        This default implementation handles common parameter filtering and
        extractor instantiation. Override this method if custom parameter
        remapping or special initialization logic is needed.

        Parameters
        ----------
        interface_kwargs : dict
            The source data parameters passed to the interface constructor.

        Returns
        -------
        extractor_instance
            An initialized extractor instance.
        """
        self.extractor_kwargs = interface_kwargs.copy()
        self.extractor_kwargs.pop("verbose", None)

        extractor_class = self.get_extractor_class()
        extractor_instance = extractor_class(**self.extractor_kwargs)
        return extractor_instance

    @property
    def extractor(self):
        """
        Get the extractor class for this interface.

        .. deprecated:: 0.8.2
            The `extractor` attribute is deprecated and will be removed on or after March 2026.
            This attribute was confusingly named as it returns a class, not an instance.
            Use the class method `get_extractor_class()`
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
        return self.get_extractor_class()

    def get_extractor(self):
        """
        Get the extractor class for this interface.

        .. deprecated:: 0.8.2
            The `get_extractor()` method is deprecated and will be removed on or after March 2026.
            This method was confusingly named as it returns a class, not an instance.
            Use `get_extractor_class()` instead.

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
        return self.get_extractor_class()
