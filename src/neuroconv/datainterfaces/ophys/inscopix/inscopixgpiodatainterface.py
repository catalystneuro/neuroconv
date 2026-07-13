from datetime import timezone

import numpy as np
from pydantic import FilePath, validate_call

from ....basedatainterface import BaseDataInterface
from ....tools import get_package
from ....utils import DeepDict

# Firmware-fixed names of the analog and monitor channels in an Inscopix ``.gpio`` file. These are the
# channels this interface writes as ``TimeSeries``; the digital lines (``Digital GPI/GPO 0-7``) and the
# BNC sync/trigger channels are event/TTL data, handled by ``InscopixGpioEventsInterface``. An explicit
# allowlist is used rather than the file's ``SignalType`` flag (which pyisx does not expose) and is
# robust against future firmware adding channels.
ANALOG_CHANNEL_NAMES = (
    "GPIO-1",
    "GPIO-2",
    "GPIO-3",
    "GPIO-4",
    "EX-LED",
    "OG-LED",
    "DI-LED",
    "e-focus",
)

# Monitor channels carry known physical units; the general-purpose ``GPIO-1..4`` inputs carry raw counts
# whose physical meaning is external experimenter knowledge, so they default to ``"a.u."``.
DEFAULT_CHANNEL_UNITS = {
    "e-focus": "micrometers",
    "EX-LED": "mW/mm^2",
    "OG-LED": "mW/mm^2",
    "DI-LED": "mW/mm^2",
}


class InscopixGpioInterface(BaseDataInterface):
    """Data interface for the analog and monitor channels of an Inscopix ``.gpio`` file.

    Inscopix stores each GPIO channel as a sparse sequence of ``(timestamp_microseconds, amplitude)``
    change-events, so each analog/monitor channel is written as its own irregular ``pynwb.TimeSeries``
    (explicit per-event ``timestamps``, never ``starting_time`` + ``rate``) in ``nwbfile.acquisition``.

    Only the eight analog/monitor channels (``GPIO-1..4``, ``EX-LED``, ``OG-LED``, ``DI-LED``,
    ``e-focus``) are written here; the digital lines and BNC sync/trigger channels are discrete events,
    handled by :class:`.InscopixGpioEventsInterface`. The two interfaces read the same file
    independently, so a conversion can run either or both.
    """

    display_name = "Inscopix GPIO"
    keywords = ("ophys", "inscopix", "gpio", "analog")
    associated_suffixes = (".gpio",)
    info = "Interface for Inscopix GPIO analog and monitor signals."

    @validate_call
    def __init__(self, file_path: FilePath, verbose: bool = False):
        """Initialize the InscopixGpioInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the ``.gpio`` Inscopix file.
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        super().__init__(file_path=file_path, verbose=verbose)

    def get_metadata(self) -> DeepDict:
        """Get metadata, setting ``session_start_time`` from the file's absolute start time.

        Returns
        -------
        DeepDict
            The metadata dictionary for this interface.
        """
        metadata = super().get_metadata()
        isx = get_package(package_name="isx")
        gpio = isx.GpioSet.read(str(self.source_data["file_path"]))
        # ``timing.start.to_datetime()`` is a naive UTC datetime (isx.Time uses utcfromtimestamp); the
        # session JSON records UTC, so attach the UTC timezone.
        session_start_time = gpio.timing.start.to_datetime().replace(tzinfo=timezone.utc)
        metadata["NWBFile"]["session_start_time"] = session_start_time
        return metadata

    def add_to_nwbfile(
        self,
        nwbfile,
        metadata: dict | None = None,
        *,
        channel_units: dict | None = None,
        channel_conversion: dict | None = None,
        stub_test: bool = False,
    ) -> None:
        """Write each present analog/monitor channel as an irregular ``TimeSeries`` into acquisition.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the analog channels to.
        metadata : dict, optional
            Metadata dictionary (unused by this interface beyond the base contract).
        channel_units : dict, optional
            Maps a channel name to the physical unit of its values, overriding the default. The
            general-purpose ``GPIO-1..4`` inputs default to ``"a.u."`` and the monitor channels to
            their known units; use this to declare a real unit for a ``GPIO`` input.
        channel_conversion : dict, optional
            Maps a channel name to a multiplicative conversion factor (``TimeSeries.conversion``);
            defaults to ``1.0``.
        stub_test : bool, optional
            If True, write only the first 100 samples of each channel (for fast testing).
        """
        from pynwb import TimeSeries

        isx = get_package(package_name="isx")
        channel_units = channel_units or {}
        channel_conversion = channel_conversion or {}

        gpio = isx.GpioSet.read(str(self.source_data["file_path"]))
        present_channels = set(gpio.channel_dict)
        for channel_name in ANALOG_CHANNEL_NAMES:
            if channel_name not in present_channels:
                continue
            timestamps_microseconds, amplitudes = gpio.get_channel_data(gpio.get_channel_index(channel_name))
            if len(timestamps_microseconds) == 0:
                continue  # a channel present but empty carries no signal; skip it
            timestamps_seconds = np.asarray(timestamps_microseconds, dtype="float64") / 1e6
            amplitudes = np.asarray(amplitudes)
            if stub_test:
                timestamps_seconds = timestamps_seconds[:100]
                amplitudes = amplitudes[:100]

            unit = channel_units.get(channel_name) or DEFAULT_CHANNEL_UNITS.get(channel_name, "a.u.")
            nwbfile.add_acquisition(
                TimeSeries(
                    name=_to_object_name_suffix(channel_name),
                    data=amplitudes,
                    timestamps=timestamps_seconds,
                    unit=unit,
                    conversion=float(channel_conversion.get(channel_name, 1.0)),
                    description=f"Inscopix GPIO analog channel '{channel_name}'.",
                )
            )


def _to_object_name_suffix(channel_name: str) -> str:
    """Turn a channel name into a valid NWB object-name suffix (no ``/``; spaces to underscores).

    The analog channel names carry no ``/`` and no spaces (``GPIO-1``, ``EX-LED``, ``e-focus``), so
    this only guards against future channels; hyphens are kept (they are valid in NWB names).
    """
    return channel_name.replace("/", "_").replace(" ", "_")
