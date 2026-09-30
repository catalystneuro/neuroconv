"""Reader for Inscopix ``.gpio`` files, independent of NWB. Private: only the GPIO interfaces use this.

A ``.gpio`` file stores each channel as a sparse ``(timestamp_microseconds, amplitude)`` change-point
sequence. pyisx reads it; this module opens the file and summarizes its channels, and nothing here knows
about NWB.
"""

import numpy as np

from ....tools import get_package


def read_gpio(file_path):
    """Open an Inscopix ``.gpio`` file with pyisx (lazily imported so isx is only needed at call time).

    pyisx does not read the ``.gpio`` itself: it converts the file into an intermediate
    ``<stem>_gpio.isxd`` in the system temporary directory and reads that. The name depends on the stem
    alone and the file is overwritten on every open, so two processes opening files of the same stem at
    once overwrite each other's copy mid-read and fail with ``Error reading file``.
    """
    isx = get_package(package_name="isx")
    return isx.GpioSet.read(str(file_path))


def get_gpio_channel_inventory(file_path) -> list[dict]:
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
    gpio = read_gpio(file_path)
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
