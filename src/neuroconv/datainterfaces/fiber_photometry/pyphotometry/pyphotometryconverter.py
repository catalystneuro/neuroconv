"""Converter for a pyPhotometry ``.ppd`` recording, its fluorescence and its digital lines together."""

from pydantic import FilePath, validate_call

from ._file_reader import _read_ppd
from .pyphotometrydatainterface import PyPhotometryFiberPhotometryInterface
from ...events.pyphotometry_events.pyphotometryeventsdatainterface import (
    PyPhotometryEventsInterface,
)
from ....nwbconverter import ConverterPipe
from ....utils import DeepDict


class PyPhotometryConverter(ConverterPipe):
    """Convert a pyPhotometry ``.ppd`` recording whole, its fluorescence and its digital lines together.

    One call writes every fluorescence signal as its own ``FiberPhotometryResponseSeries`` and every
    digital line as its own ``EventsTable``. How many of each a recording holds depends on how it was
    acquired, and ``get_available_streams`` lists them before you build anything.

    Each series is named after the stream its signal came off,
    ``FiberPhotometryResponseSeriesDetector1Excitation1``, so several of them can sit in one file. The
    ``FiberPhotometry`` metadata (devices, indicators, table rows, per-series regions) is yours to supply,
    exactly as for one interface on its own.
    """

    display_name = "pyPhotometry Converter"
    keywords = ("fiber photometry", "events", "pyPhotometry")
    associated_suffixes = (".ppd",)
    info = "Converts every fluorescence signal and digital line of a pyPhotometry recording."

    @classmethod
    def get_available_streams(cls, file_path: FilePath) -> list[str]:
        """Return every signal and line a file holds: the fluorescence signals first, then the lines."""
        analog_streams, digital_lines = cls._read_stream_names(file_path=file_path)
        return analog_streams + digital_lines

    @staticmethod
    def _read_stream_names(*, file_path: FilePath) -> tuple[list[str], list[str]]:
        """Return the file's signal names and line names separately, each in interleave order."""
        recording = _read_ppd(file_path)
        analog_streams = [
            PyPhotometryFiberPhotometryInterface._stream_name(signal) for signal in recording.analog_signals
        ]
        digital_lines = [
            PyPhotometryEventsInterface._signal_source_id(digital_signal)
            for digital_signal in recording.digital_signals
        ]
        return analog_streams, digital_lines

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        detection_configuration: dict | None = None,
        verbose: bool = False,
    ):
        """Build an interface for every signal and line of a ``.ppd`` file.

        Parameters
        ----------
        file_path : FilePath
            The ``.ppd`` file.
        detection_configuration : dict, optional
            Forwarded to :class:`.PyPhotometryEventsInterface`, which documents it. It names the lines to
            read as well as how to read them, so it is also how a line is left out. When None (default)
            every line the file carries is read as a ``high_period``.
        verbose : bool, default: False
            Whether to print status messages.
        """
        analog_streams, digital_lines = self._read_stream_names(file_path=file_path)

        data_interfaces = {}
        # interface name -> the name its response series takes, applied in get_metadata below.
        self._series_names: dict[str, str] = {}
        for stream_name in analog_streams:
            interface_name = f"FiberPhotometry_{stream_name}"
            data_interfaces[interface_name] = PyPhotometryFiberPhotometryInterface(
                file_path=file_path, stream_name=stream_name, verbose=verbose
            )
            self._series_names[interface_name] = "FiberPhotometryResponseSeries" + "".join(
                part.capitalize() for part in stream_name.split("_")
            )

        if digital_lines:
            # One interface covers every line, since it addresses them by name and reads whichever the
            # configuration asks for.
            data_interfaces["Events"] = PyPhotometryEventsInterface(
                file_path=file_path,
                detection_configuration=detection_configuration,
                verbose=verbose,
            )

        super().__init__(data_interfaces=data_interfaces, verbose=verbose)

    def get_metadata(self) -> DeepDict:
        """Merge the sub-interfaces' metadata, giving each response series a name of its own.

        Every single-series interface defaults to the same ``FiberPhotometryResponseSeries``, which is
        unique only in a file holding one signal, so each is suffixed here with the slot it came off.
        """
        metadata = super().get_metadata()
        for interface_name, series_name in self._series_names.items():
            metadata_key = self.data_interface_objects[interface_name].metadata_key
            metadata["FiberPhotometry"][metadata_key]["name"] = series_name
        return metadata
