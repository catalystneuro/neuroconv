import re
from datetime import timezone

import numpy as np
from pydantic import FilePath, validate_call

from ....basedatainterface import BaseDataInterface
from ....tools import get_package
from ....utils import DeepDict

# Monitor channels carry known physical units; every other channel (the general-purpose GPIO inputs,
# the digital lines, the BNC lines) carries raw counts whose physical meaning is external experimenter
# knowledge, so it defaults to "a.u.".
_DEFAULT_CHANNEL_UNITS = {
    "e-focus": "micrometers",
    "EX-LED": "mW/mm^2",
    "OG-LED": "mW/mm^2",
    "DI-LED": "mW/mm^2",
}


def _read_gpio(file_path):
    """Open an Inscopix ``.gpio`` file with pyisx (lazily imported so isx is only needed at call time)."""
    isx = get_package(package_name="isx")
    return isx.GpioSet.read(str(file_path))


def _get_gpio_channel_inventory(file_path) -> list[dict]:
    """List every channel in a ``.gpio`` file, to help decide what to convert and how.

    The Inscopix file records no analog-vs-digital flag (see the format notes), so which channels are
    continuous signals versus discrete events is a human call. This returns, per channel, its name,
    sample count, and value set/range, so a user can eyeball which lines are 0/1 (digital), which are
    multi-level codes, and which are continuous, and pick ``exclude_channels`` /
    ``detection_configuration`` / ``binarize`` accordingly.

    Returns
    -------
    list of dict
        One dict per channel: ``name``, ``num_samples``, ``num_unique``, ``unique_values`` (up to 8),
        ``min``, ``max``.
    """
    gpio = _read_gpio(file_path)
    inventory = []
    for index in range(gpio.num_channels):
        name = gpio.get_channel_name(index)
        timestamps, amplitudes = gpio.get_channel_data(index)
        amplitudes = np.asarray(amplitudes)
        unique = np.unique(amplitudes)
        inventory.append(
            {
                "name": name,
                "num_samples": int(len(timestamps)),
                "num_unique": int(len(unique)),
                "unique_values": unique[:8].tolist(),
                "min": float(amplitudes.min()) if len(amplitudes) else None,
                "max": float(amplitudes.max()) if len(amplitudes) else None,
            }
        )
    return inventory


class InscopixGpioInterface(BaseDataInterface):
    """Data interface for the channels of an Inscopix ``.gpio`` file, written as ``TimeSeries``.

    Inscopix stores each GPIO channel as a sparse ``(timestamp_microseconds, amplitude)`` change-point
    sequence, so each channel is written as its own irregular ``pynwb.TimeSeries`` (explicit per-event
    ``timestamps``, never ``starting_time`` + ``rate``) in ``nwbfile.acquisition``.

    **All present channels are written by default**, because storing a raw trace is always faithful
    regardless of whether a channel is a continuous signal or a discrete line, and the file records no
    way to tell them apart. Use ``exclude_channels`` to drop channels you do not want. The monitor
    channels (``EX-LED``, ``OG-LED``, ``DI-LED``, ``e-focus``) get their known physical units; every
    other channel carries no unit the file can state, so it is written as ``"a.u."`` unless the
    ``metadata["TimeSeries"]`` entry this interface seeds for it says otherwise.

    Discrete events (edges, coded levels) are a separate, additive product handled by
    :class:`.InscopixGpioEventsInterface`; the two interfaces read the same file independently.
    """

    display_name = "Inscopix GPIO"
    keywords = ("ophys", "inscopix", "gpio", "analog")
    associated_suffixes = (".gpio",)
    info = "Interface for Inscopix GPIO channels written as TimeSeries."

    @validate_call
    def __init__(
        self,
        file_path: FilePath,
        *,
        exclude_channels: list[str] | None = None,
        metadata_key: str = "inscopix_gpio",
        verbose: bool = False,
    ):
        """Initialize the InscopixGpioInterface.

        Parameters
        ----------
        file_path : FilePath
            Path to the ``.gpio`` Inscopix file.
        exclude_channels : list of str, optional
            Names of channels to skip. If None (default), every present channel is written.
        metadata_key : str, optional
            Namespaces this interface's entries in ``metadata["TimeSeries"]``, one per written channel.
        verbose : bool, optional
            Whether to print status messages, default = False.
        """
        super().__init__(file_path=file_path, exclude_channels=exclude_channels, verbose=verbose)
        self.metadata_key = metadata_key

    @classmethod
    def get_available_channels(cls, file_path) -> list[dict]:
        """Return one dict per channel of a ``.gpio`` file, to decide what to convert and how.

        Each dict carries the channel's ``name``, ``num_samples``, ``num_unique``, ``unique_values``
        (up to eight), ``min`` and ``max``. The file records no analog-versus-digital flag, so this is
        what tells you which channels are worth writing and which to pass to ``exclude_channels``.
        """
        return _get_gpio_channel_inventory(file_path)

    def _get_channel_metadata_key(self, channel_name: str) -> str:
        """The ``metadata["TimeSeries"]`` key this interface addresses one channel by."""
        return f"{self.metadata_key}_{_to_snake_case(channel_name)}"

    def get_metadata(self) -> DeepDict:
        """Get metadata: the session start time, and one ``TimeSeries`` entry per written channel.

        Each entry carries the object ``name`` and a ``description``, and a ``unit`` only for the monitor
        channels, whose units the format fixes. Every other channel records no unit, so the entry states
        none and the writer falls back to ``"a.u."``. A user who knows what a channel measures says so by
        setting ``unit``, and scales it with ``conversion``, in that entry, the way the analog recording
        interfaces are edited.
        """
        metadata = super().get_metadata()
        gpio = _read_gpio(self.source_data["file_path"])
        # ``timing.start.to_datetime()`` is a naive UTC datetime (isx.Time uses utcfromtimestamp).
        metadata["NWBFile"]["session_start_time"] = gpio.timing.start.to_datetime().replace(tzinfo=timezone.utc)

        exclude = set(self.source_data.get("exclude_channels") or [])
        time_series_metadata = {}
        for index in range(gpio.num_channels):
            channel_name = gpio.get_channel_name(index)
            if channel_name in exclude:
                continue
            entry = dict(
                name=_to_object_name(channel_name),
                description=f"Inscopix GPIO channel '{channel_name}'.",
            )
            if channel_name in _DEFAULT_CHANNEL_UNITS:
                entry["unit"] = _DEFAULT_CHANNEL_UNITS[channel_name]
            time_series_metadata[self._get_channel_metadata_key(channel_name)] = entry
        metadata["TimeSeries"] = time_series_metadata

        return metadata

    def add_to_nwbfile(
        self,
        nwbfile,
        metadata: dict | None = None,
        *,
        stub_test: bool = False,
    ) -> None:
        """Write every present, non-excluded channel as an irregular ``TimeSeries`` into acquisition.

        Parameters
        ----------
        nwbfile : NWBFile
            The NWB file to add the channels to.
        metadata : dict, optional
            Metadata dictionary. Each channel is written from its own ``metadata["TimeSeries"]`` entry,
            which carries the object ``name``, its ``description``, and optionally the ``unit`` and the
            ``conversion`` scaling the stored values into it. Defaults to ``self.get_metadata()``.
        stub_test : bool, optional
            If True, write only the first 100 samples of each channel (for fast testing).
        """
        from pynwb import TimeSeries

        metadata = metadata or self.get_metadata()
        time_series_metadata = metadata.get("TimeSeries", {})
        exclude = set(self.source_data.get("exclude_channels") or [])

        gpio = _read_gpio(self.source_data["file_path"])
        for index in range(gpio.num_channels):
            channel_name = gpio.get_channel_name(index)
            if channel_name in exclude:
                continue
            timestamps_microseconds, amplitudes = gpio.get_channel_data(index)
            if len(timestamps_microseconds) == 0:
                continue  # a channel present but empty carries no signal; skip it
            timestamps_seconds = np.asarray(timestamps_microseconds, dtype="float64") / 1e6
            amplitudes = np.asarray(amplitudes)
            if stub_test:
                timestamps_seconds = timestamps_seconds[:100]
                amplitudes = amplitudes[:100]

            channel_metadata = dict(time_series_metadata.get(self._get_channel_metadata_key(channel_name), {}))
            # ``unit`` is required by ``TimeSeries`` and this format states one only for the monitor
            # channels, so the rest are defaulted here rather than in ``get_metadata``, which would be
            # asserting a unit the file never recorded.
            channel_metadata.setdefault("name", _to_object_name(channel_name))
            channel_metadata.setdefault("unit", "a.u.")
            nwbfile.add_acquisition(TimeSeries(data=amplitudes, timestamps=timestamps_seconds, **channel_metadata))


def _to_object_name(channel_name: str) -> str:
    """Turn a channel name into a valid NWB object name (no ``/``; spaces to underscores; hyphens kept)."""
    return channel_name.replace("/", "_").replace(" ", "_")


def _to_snake_case(name: str) -> str:
    """``"BNC Sync Output"`` -> ``bnc_sync_output`` (a lowercase name the base writer CamelCases cleanly)."""
    return re.sub(r"_+", "_", re.sub(r"[^0-9a-zA-Z]+", "_", name)).strip("_").lower()
