from typing import Literal

from pynwb import NWBFile

from ...basedatainterface import BaseDataInterface
from ...utils import DeepDict


class BaseRecordingToTimeSeriesInterface(BaseDataInterface):
    """
    Base for the interfaces that write a recording as a ``TimeSeries`` instead of an ``ElectricalSeries``.

    These are the channels an acquisition system records next to the electrodes: auxiliary and analog
    inputs, trigger and synchronization lines, and stimulation currents. They do not belong in an
    ``ElectricalSeries``, which is for electrical recordings from electrodes.

    A subclass reads its source into ``self.recording_extractor``, states ``self.metadata_key``, and
    names the series through ``_get_time_series_name`` and ``_get_time_series_description``. A subclass
    whose metadata carries more than the series, a session start time or a device, overrides
    ``get_metadata`` and calls ``super()`` first.

    A ``TimeSeries`` states one unit for all of its channels, so an interface here holds channels of one
    unit. Where a source mixes them, select one unit per interface rather than writing them together.
    """

    # Where the series is written. A signal applied to the preparation is stimulus, a recorded one is
    # acquisition, and the writer defaults to acquisition.
    parent_container: Literal["acquisition", "stimulus"] = "acquisition"

    @property
    def channel_ids(self):
        """The ids of the channels this interface holds, in the order they are written."""
        return self.recording_extractor.get_channel_ids()

    def get_channel_names(self) -> list[str]:
        """
        Get the names of the channels this interface holds.

        Returns
        -------
        list of str
            The channel names, in the order they are written.
        """
        return list(self.recording_extractor.get_channel_ids())

    def _get_time_series_name(self) -> str:
        """The name of the written ``TimeSeries``. Subclasses state their own."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement `_get_time_series_name` to name the TimeSeries it writes."
        )

    def _get_time_series_description(self) -> str:
        """The description of the written ``TimeSeries``. Subclasses state their own."""
        raise NotImplementedError(
            f"{type(self).__name__} must implement `_get_time_series_description` to describe the TimeSeries it writes."
        )

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        # Assigned per key rather than replacing the block, so a subclass that filled it first keeps
        # what it put there.
        metadata["TimeSeries"][self.metadata_key] = dict(
            name=self._get_time_series_name(),
            description=self._get_time_series_description(),
        )

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *,
        stub_test: bool = False,
        iterator_type: str | None = "v2",
        iterator_options: dict | None = None,
        always_write_timestamps: bool = False,
    ):
        """
        Write this interface's channels to the NWBFile as a ``TimeSeries``.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to write to.
        metadata : dict, optional
            Metadata dictionary. If None, ``get_metadata()`` is used.
        stub_test : bool, default: False
            If True, only a small amount of data is written.
        iterator_type : str, optional, default: "v2"
            Type of iterator to use for data streaming.
        iterator_options : dict, optional
            Additional options for the iterator.
        always_write_timestamps : bool, default: False
            If True, timestamps are always written instead of a sampling rate.
        """
        from ...tools.spikeinterface import (
            _stub_recording,
            add_recording_as_time_series_to_nwbfile,
        )

        if metadata is None:
            metadata = self.get_metadata()

        recording = self.recording_extractor
        if stub_test:
            recording = _stub_recording(recording=recording)

        add_recording_as_time_series_to_nwbfile(
            recording=recording,
            nwbfile=nwbfile,
            metadata=metadata,
            iterator_type=iterator_type,
            iterator_options=iterator_options,
            always_write_timestamps=always_write_timestamps,
            metadata_key=self.metadata_key,
            parent_container=self.parent_container,
        )
