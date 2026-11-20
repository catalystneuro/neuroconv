from abc import abstractmethod

import numpy as np

from .baseethograminterface import BaseEthogramInterface
from ..._temporal_alignment import _TemporalAlignment
from ...tools.signal_processing import _run_length_encode_labels

__all__ = ["BaseBehavioralSegmentationInterface"]


class BaseBehavioralSegmentationInterface(BaseEthogramInterface):
    """Base class for interfaces of behavioral segmentation tools, which assign one behavior label to every frame.

    A subclass supplies the per-frame labels and the native time of each frame. The base registers those times in
    ``temporal_alignment`` under the interface's ``metadata_key``, run-length encodes the labels on the aligned
    times into one bout per run of a label, and catalogues one behavior per label present.
    """

    keywords = ("behavior", "ethogram", "behavioral segmentation")

    labeling_method = "automated"
    bout_concurrency = "partition"
    behavior_definition: str = ""
    """The ``definition`` of every catalogue row, since a segmentation tool assigns ids, not described behaviors."""

    def __init__(self, verbose: bool = False, **source_data):
        super().__init__(verbose=verbose, **source_data)
        self.temporal_alignment = _TemporalAlignment()
        self.temporal_alignment._add_time_bearing_object(
            key=self.metadata_key,
            get_native_times=self._get_native_times,
            get_number_of_samples=lambda: len(self._get_labels()),
        )

    @abstractmethod
    def _get_labels(self) -> np.ndarray:
        """Return the integer label of every frame."""

    @abstractmethod
    def _get_native_times(self) -> np.ndarray:
        """Return the time of every frame, in seconds, before any alignment."""

    def _get_behaviors(self) -> list[dict]:
        return [
            dict(behavior=str(label), definition=self.behavior_definition, native_code=int(label))
            for label in np.unique(self._get_labels())
        ]

    def _get_bouts(self) -> dict:
        runs = _run_length_encode_labels(self._get_labels(), self.temporal_alignment[self.metadata_key].get_times())
        return dict(
            start_times=[start_time for start_time, _, _ in runs],
            stop_times=[stop_time for _, stop_time, _ in runs],
            labels=[str(label) for _, _, label in runs],
        )
