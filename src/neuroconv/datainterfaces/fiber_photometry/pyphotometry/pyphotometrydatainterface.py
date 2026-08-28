"""Interface for pyPhotometry ``.ppd`` recordings."""

from datetime import datetime

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import NWBFile

from ._file_reader import _PPDRecording, _read_ppd
from ..basefiberphotometryinterface import BaseFiberPhotometryInterface
from ....tools import get_package
from ....utils import DeepDict, dict_deep_update


class PyPhotometryFiberPhotometryInterface(BaseFiberPhotometryInterface):
    """Interface for one signal of a pyPhotometry ``.ppd`` recording.

    A ``.ppd`` holds every signal the board recorded and no two of them were sampled at the same instant,
    so one interface reads one signal. Combine several in a converter to write them into one file.

    Streams are named for the photodetector read and the excitation source lit, as in
    ``detector_1_excitation_2``, and a shared ``detector`` prefix means those signals came off one fiber.
    Use :meth:`get_available_streams` to list what a file holds.
    """

    display_name = "pyPhotometry Fiber Photometry"
    associated_suffixes = (".ppd",)
    info = "Interface for pyPhotometry fiber photometry recordings."

    @classmethod
    def get_available_streams(cls, file_path: FilePath) -> list[str]:
        """Return the names of the signals in a file, in the order the words interleave them."""
        return [cls._stream_name(signal) for signal in _read_ppd(file_path).analog_signals]

    @staticmethod
    def _stream_name(signal) -> str:
        """Name a signal by the photodetector read and the excitation source lit, counting from one.

        Those are the two devices a ``FiberPhotometryTable`` row links, so a shared ``detector`` prefix
        says which signals came off one fiber.
        """
        return f"detector_{signal.detector_index + 1}_excitation_{signal.excitation_index + 1}"

    @validate_call(config=dict(arbitrary_types_allowed=True))
    def __init__(
        self,
        file_path: FilePath,
        *,
        stream_name: str | None = None,
        metadata_key: str | None = None,
        verbose: bool = False,
    ):
        """Initialize the interface for one signal of a ``.ppd`` file.

        Parameters
        ----------
        file_path : path
            The ``.ppd`` file.
        stream_name : str, optional
            Which signal to read, as named by :meth:`get_available_streams`. Defaults to the first
            signal, which is only unambiguous on a file that holds one.
        metadata_key : str, optional
            Key under ``metadata["FiberPhotometry"]`` for this interface's response series. Defaults to
            one derived from the stream name.
        verbose : bool, default: False
            Whether to print status messages.
        """
        self._file_path = file_path
        self._cached_recording: _PPDRecording | None = None

        available_streams = self.get_available_streams(file_path=file_path)
        if stream_name is None:
            stream_name = available_streams[0]
        elif stream_name not in available_streams:
            raise ValueError(
                f"'{stream_name}' is not a signal of '{file_path}', which holds {available_streams}. "
                "The signals a file carries are decided by its acquisition mode."
            )

        super().__init__(
            stream_names=stream_name,
            metadata_key=metadata_key,
            verbose=verbose,
            file_path=str(file_path),
        )

    @property
    def _recording(self) -> _PPDRecording:
        """The file, read once and kept, since a photometry session is small enough to hold."""
        if self._cached_recording is None:
            self._cached_recording = _read_ppd(self._file_path)
        return self._cached_recording

    def _get_signal(self, stream_name: str):
        """Return the signal a stream name refers to, validated against the file at construction."""
        return {self._stream_name(signal): signal for signal in self._recording.analog_signals}[stream_name]

    def _get_stream_data(self, *, stream_name: str) -> np.ndarray:
        return self._get_signal(stream_name).data_in_volts

    def _get_stream_timestamps(self, *, stream_name: str) -> np.ndarray:
        """Return this signal's own times, beginning at the instant its slot was sampled.

        The samples are regular, so this expands a start time and a rate into the array the base class
        expects and collapses back to a rate on write.
        """
        signal = self._get_signal(stream_name)
        sample_count = len(signal.data_in_volts)
        return signal.starting_time_in_seconds + np.arange(sample_count) / signal.rate_in_hz

    def get_metadata(self) -> DeepDict:
        """Add what the header states about the session and the subject, and what it omits about timing."""
        metadata = super().get_metadata()
        date_time = self._recording.header.get("date_time")
        if date_time is not None:
            metadata = dict_deep_update(
                metadata, dict(NWBFile=dict(session_start_time=datetime.fromisoformat(date_time)))
            )
        # The identifier typed into the acquisition GUI, and the only thing a .ppd says about the animal.
        # Every header generation carries the field, so an empty one means it was left blank rather than
        # that the format lacks it, and writing that would be indistinguishable from an experimenter
        # naming their subject "".
        subject_id = self._recording.header.get("subject_ID")
        if subject_id:
            metadata = dict_deep_update(metadata, dict(Subject=dict(subject_id=subject_id)))
        if not self._recording.pulsed:
            # A comment rather than a description, since it says how the recording was made rather than
            # what the data is. The firmware reads the analog inputs one after the other inside a single
            # timer interrupt, and the format's author has measured that delay, but on one board and with
            # an interrupt routine modified to drive the LEDs, so it is a property of the hardware rather
            # than of this recording. It is reported rather than applied: the header carries neither the
            # oversampling buffer nor its clock, so a start time built from it would look like something
            # the file states.
            comments = (
                "Acquired in a continuous mode, in which the board reads its analog inputs sequentially "
                "within one timer interrupt rather than sampling them simultaneously, so a signal is "
                "later than the one read before it. The format's author measured this delay at a mean of "
                "393 microseconds with a standard deviation of 9 microseconds, reported in "
                "https://github.com/pyPhotometry/code/issues/39. That figure is a property of the board "
                "and its firmware rather than of this file, which records neither the oversampling buffer "
                "nor its clock, so it is not applied here: every signal is written on the timebase the "
                "header states, as pyPhotometry's own reader does."
            )
            metadata = dict_deep_update(metadata, dict(FiberPhotometry={self.metadata_key: dict(comments=comments)}))
        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        *,
        stub_test: bool = False,
        stub_samples: int = 100,
        always_write_timestamps: bool = False,
        **conversion_options,
    ) -> None:
        """Write the response series, and the raw pair beside it when the file carries one.

        From header version 1.1 a strobed recording stores the LED-on sample and the LED-off baseline it
        was measured against. The response series carries their difference, which is what earlier
        firmware wrote itself, and both measurements are written beside it.

        ``RawLEDOn`` references the same ``FiberPhotometryTable`` row as the difference. ``RawBaseline``
        references none, since a row states an excitation source and wavelength and a measurement taken
        in the dark had neither.
        """
        super().add_to_nwbfile(
            nwbfile=nwbfile,
            metadata=metadata,
            stub_test=stub_test,
            stub_samples=stub_samples,
            always_write_timestamps=always_write_timestamps,
            **conversion_options,
        )

        signal = self._get_signal(self.stream_names[0])
        if signal.raw_led_on_in_volts is None:
            return

        FiberPhotometryResponseSeries = get_package(package_name="ndx_fiber_photometry").FiberPhotometryResponseSeries

        series_name = (metadata or self.get_metadata())["FiberPhotometry"][self.metadata_key]["name"]
        response_series = nwbfile.acquisition[series_name]
        table_region = getattr(response_series, "fiber_photometry_table_region", None)

        # The raw pair is the difference before the subtraction, so it is cut and timed exactly as the
        # difference was: same aligned times, same stub, same choice between a rate and an array.
        def stub(array: np.ndarray) -> np.ndarray:
            return array[: min(stub_samples, len(array))] if stub_test else array

        timing_kwargs = self._timing_kwargs_from_timestamps(
            stub(self.alignment[self.metadata_key].get_times()), always_write_timestamps
        )

        # The LED-on trace is the difference before the subtraction, so every field of the row the
        # difference references is true of it as well. A region belongs to one series, so it gets its
        # own over those same rows rather than sharing the object.
        led_on_region = (
            table_region.table.create_fiber_photometry_table_region(
                description=table_region.description, region=list(table_region.data)
            )
            if table_region is not None
            else None
        )
        nwbfile.add_acquisition(
            FiberPhotometryResponseSeries(
                name=f"{series_name}RawLEDOn",
                data=stub(signal.raw_led_on_in_volts),
                unit="volts",
                description=(
                    "The measurement taken with the excitation LED on, before the baseline recorded "
                    "beside it was subtracted. Written because the acquisition system measured it."
                ),
                fiber_photometry_table_region=led_on_region,
                **timing_kwargs,
            )
        )

        # The dark measurement was taken with no excitation at all, and a row requires an excitation
        # source and an excitation wavelength, so any row written for it would name one that was never
        # applied. It goes in unlinked, saying in its description what it is.
        nwbfile.add_acquisition(
            FiberPhotometryResponseSeries(
                name=f"{series_name}RawBaseline",
                data=stub(signal.raw_baseline_in_volts),
                unit="volts",
                description=(
                    "The measurement taken with the excitation LED off, which the LED-on sample is "
                    "corrected against. It measures ambient light and detector offset at that instant. "
                    "It references no FiberPhotometryTable row because a row states an excitation source "
                    "and wavelength, and neither applies to a measurement taken in the dark."
                ),
                fiber_photometry_table_region=None,
                **timing_kwargs,
            )
        )
