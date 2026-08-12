"""Interface for pyPhotometry ``.ppd`` recordings."""

from datetime import datetime

import numpy as np
from pydantic import FilePath, validate_call
from pynwb import NWBFile, TimeSeries

from ._ppd_file_reader import PPDRecording, read_ppd
from ..basefiberphotometryinterface import BaseFiberPhotometryInterface
from ....utils import DeepDict, dict_deep_update

#: Said in the series rather than in its timestamps, because the size of the lag is not knowable from
#: the file. The firmware reads the analog inputs one after the other inside a single timer interrupt,
#: so the second one is late by the 64-sample oversampling buffer at the 300 kHz oversampling clock,
#: plus interrupt work nobody has quantified. Neither constant is in the header, and no pyPhotometry
#: document states the resulting offset, so writing a number here would look measured while being, at
#: best, a floor.
_CONTINUOUS_TIMING_DESCRIPTION = (
    "Acquired in a continuous mode, in which the board reads its analog inputs sequentially within one "
    "timer interrupt rather than sampling them simultaneously. A signal is therefore later than the one "
    "read before it by at least 213 microseconds (a 64-sample oversampling buffer at the firmware's 300 "
    "kHz oversampling clock) plus unquantified interrupt overhead. The file records neither constant and "
    "the offset has never been characterized upstream, so every signal here is written on the timebase "
    "the header states, as pyPhotometry's own reader does."
)


class PyPhotometryFiberPhotometryInterface(BaseFiberPhotometryInterface):
    """Interface for one signal of a pyPhotometry ``.ppd`` recording.

    A ``.ppd`` file holds every signal the board recorded, interleaved word by word, and no two of them
    were sampled at the same instant: in the pulsed modes the timer advances one analog line per tick, so
    a response series can only ever carry one of them. Each signal therefore gets its own interface, the
    way the Neurophotometrics interface takes one excitation at a time, and several of them are combined
    by putting them in a converter of your own.

    Signals are named the way pyPhotometry's own reader names them, ``analog_1`` and ``analog_2``. The
    four-color fork, whose analog lines each multiplex two colors, extends that to ``analog_1_color_1``
    and so on. Use :meth:`get_available_streams` to list what a file actually holds.
    """

    display_name = "pyPhotometry Fiber Photometry"
    associated_suffixes = (".ppd",)
    info = "Interface for pyPhotometry fiber photometry recordings."

    @classmethod
    def get_available_streams(cls, file_path: FilePath) -> list[str]:
        """Return the names of the signals in a file, in the order the words interleave them."""
        return [cls._stream_name(signal) for signal in read_ppd(file_path).analog_signals]

    @staticmethod
    def _stream_name(signal) -> str:
        """Name a signal after the analog line it came off, counting from one as the vendor does."""
        name = f"analog_{signal.analog_input + 1}"
        return name if signal.color_index == 0 else f"{name}_color_{signal.color_index + 1}"

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
        self.file_path = file_path
        self._recording: PPDRecording | None = None

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
    def recording(self) -> PPDRecording:
        """The file, read once and kept, since a photometry session is small enough to hold."""
        if self._recording is None:
            self._recording = read_ppd(self.file_path)
        return self._recording

    def _get_signal(self, stream_name: str):
        for signal in self.recording.analog_signals:
            if self._stream_name(signal) == stream_name:
                return signal
        raise ValueError(f"'{stream_name}' is not a signal of '{self.file_path}'.")

    def _get_stream_data(self, *, stream_name: str) -> np.ndarray:
        return self._get_signal(stream_name).data_in_volts

    def _get_stream_timestamps(self, *, stream_name: str) -> np.ndarray:
        """Return this signal's own times.

        The signal is regular, so this is a start time and a rate expanded into an array, which is what
        the base class expects and which it collapses back to a rate when it writes. The start time is
        the point: the file's signals were sampled one after another, and the upstream reader reports
        every one of them as starting at zero.
        """
        signal = self._get_signal(stream_name)
        sample_count = len(signal.data_in_volts)
        return signal.starting_time_in_seconds + np.arange(sample_count) / signal.rate_in_hz

    def get_metadata(self) -> DeepDict:
        """Add what the header states about the session, and what it fails to state about the timing."""
        metadata = super().get_metadata()
        date_time = self.recording.header.get("date_time")
        if date_time is not None:
            metadata = dict_deep_update(
                metadata, dict(NWBFile=dict(session_start_time=datetime.fromisoformat(date_time)))
            )
        if not self.recording.pulsed:
            metadata = dict_deep_update(
                metadata,
                dict(FiberPhotometry={self.metadata_key: dict(description=_CONTINUOUS_TIMING_DESCRIPTION)}),
            )
        return metadata

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        **conversion_options,
    ) -> None:
        """Write the response series, and the raw pair beside it when the file carries one.

        From header version 1.1 a pulsed file stores the LED-on sample and the LED-off baseline it was
        measured against, and the subtraction that used to happen on the board moved into the reader. The
        response series carries the difference, which is the quantity every pipeline expects and the one
        earlier firmware wrote itself. The two measurements it came from are written beside it as plain
        ``TimeSeries``: they are real measurements, so dropping them would destroy data, but neither is a
        response of an indicator to an excitation, and the baseline was taken with the LED dark, so
        neither belongs in a ``FiberPhotometryTable`` row.
        """
        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, **conversion_options)

        signal = self._get_signal(self.stream_names[0])
        if signal.raw_led_on_in_volts is None:
            return

        series_name = (metadata or self.get_metadata())["FiberPhotometry"][self.metadata_key]["name"]
        timestamps = self.get_timestamps()
        starting_time, rate = float(timestamps[0]), float(signal.rate_in_hz)
        for suffix, data, description in (
            (
                "RawLEDOn",
                signal.raw_led_on_in_volts,
                "The measurement taken with the excitation LED on, before the baseline recorded beside "
                "it was subtracted. Written because the acquisition system measured it.",
            ),
            (
                "RawBaseline",
                signal.raw_baseline_in_volts,
                "The measurement taken with the excitation LED off, which the LED-on sample is corrected "
                "against. It measures ambient light and detector offset at that instant.",
            ),
        ):
            nwbfile.add_acquisition(
                TimeSeries(
                    name=f"{series_name}{suffix}",
                    data=data,
                    unit="volts",
                    starting_time=starting_time,
                    rate=rate,
                    description=description,
                )
            )
