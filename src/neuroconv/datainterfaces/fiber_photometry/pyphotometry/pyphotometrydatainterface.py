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

    A ``.ppd`` file holds every signal the board recorded, interleaved word by word, and no two of them
    were sampled at the same instant: in the pulsed modes the timer advances one analog line per tick, so
    a response series can only ever carry one of them. Each signal therefore gets its own interface, the
    way the Neurophotometrics interface takes one excitation at a time, and several of them are combined
    by putting them in a converter of your own.

    Signals are named for the photodetector read and the excitation source lit, so a recording strobing
    two sources onto one detector offers ``detector_1_excitation_1`` and ``detector_1_excitation_2``,
    while one using a detector per source offers ``detector_1_excitation_1`` and
    ``detector_2_excitation_2``. A shared ``detector`` prefix means a shared optical fiber, and so one
    brain region across those series. Use :meth:`get_available_streams` to list what a file holds.
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
        for signal in self._recording.analog_signals:
            if self._stream_name(signal) == stream_name:
                return signal
        raise ValueError(f"'{stream_name}' is not a signal of '{self._file_path}'.")

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
            # Said in the series rather than in its timestamps, because the size of the lag is not
            # knowable from the file. The firmware reads the analog inputs one after the other inside a
            # single timer interrupt, so the second is late by the 64-sample oversampling buffer at the
            # 300 kHz oversampling clock, plus interrupt work nobody has quantified. Neither constant is
            # in the header, so writing a number would look measured while being, at best, a floor.
            description = (
                "Acquired in a continuous mode, in which the board reads its analog inputs sequentially "
                "within one timer interrupt rather than sampling them simultaneously. A signal is "
                "therefore later than the one read before it by at least 213 microseconds (a 64-sample "
                "oversampling buffer at the firmware's 300 kHz oversampling clock) plus unquantified "
                "interrupt overhead. The file records neither constant and the offset has never been "
                "characterized upstream, so every signal here is written on the timebase the header "
                "states, as pyPhotometry's own reader does."
            )
            metadata = dict_deep_update(
                metadata, dict(FiberPhotometry={self.metadata_key: dict(description=description)})
            )
        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
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
        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, **conversion_options)

        signal = self._get_signal(self.stream_names[0])
        if signal.raw_led_on_in_volts is None:
            return

        FiberPhotometryResponseSeries = get_package(package_name="ndx_fiber_photometry").FiberPhotometryResponseSeries

        series_name = (metadata or self.get_metadata())["FiberPhotometry"][self.metadata_key]["name"]
        response_series = nwbfile.acquisition[series_name]
        table_region = getattr(response_series, "fiber_photometry_table_region", None)
        starting_time, rate = float(self.get_timestamps()[0]), float(signal.rate_in_hz)

        for suffix, data, description, links_to_the_row in (
            (
                "RawLEDOn",
                signal.raw_led_on_in_volts,
                "The measurement taken with the excitation LED on, before the baseline recorded beside "
                "it was subtracted. Written because the acquisition system measured it.",
                True,
            ),
            (
                "RawBaseline",
                signal.raw_baseline_in_volts,
                "The measurement taken with the excitation LED off, which the LED-on sample is corrected "
                "against. It measures ambient light and detector offset at that instant. It references no "
                "FiberPhotometryTable row because a row states an excitation source and wavelength, and "
                "neither applies to a measurement taken in the dark.",
                False,
            ),
        ):
            # A region belongs to one series, so the LED-on trace gets its own over the rows the
            # difference uses rather than sharing the object.
            own_region = (
                table_region.table.create_fiber_photometry_table_region(
                    description=table_region.description, region=list(table_region.data)
                )
                if links_to_the_row and table_region is not None
                else None
            )
            nwbfile.add_acquisition(
                FiberPhotometryResponseSeries(
                    name=f"{series_name}{suffix}",
                    data=data,
                    unit="volts",
                    starting_time=starting_time,
                    rate=rate,
                    description=description,
                    fiber_photometry_table_region=own_region,
                )
            )
