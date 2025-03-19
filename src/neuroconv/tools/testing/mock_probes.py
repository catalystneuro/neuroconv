import numpy as np


def generate_mock_probe(num_channels: int, num_shanks: int = 3):
    """
    Generate a mock probe with specified number of channels and shanks.

    Parameters:
        num_channels (int): The number of channels in the probe.
        num_shanks (int, optional): The number of shanks in the probe. Defaults to 3.

    Returns:
        pi.Probe: The generated mock probe.

    """
    import probeinterface as pi

    # The shank ids will be 0, 0, 0, ..., 1, 1, 1, ..., 2, 2, 2, ...
    shank_ids: list[int] = []
    positions = np.zeros((num_channels, 2))
    # ceil division
    channels_per_shank = (num_channels + num_shanks - 1) // num_shanks
    for i in range(num_shanks):
        # x0, y0 is the position of the first electrode in the shank
        x0 = 0
        y0 = i * 200
        for j in range(channels_per_shank):
            if len(shank_ids) == num_channels:
                break
            shank_ids.append(i)
            x = x0 + j * 10
            y = y0 + (j % 2) * 10
            positions[len(shank_ids) - 1] = x, y
    probe = pi.Probe(ndim=2, si_units="um")
    probe.set_contacts(positions=positions, shapes="circle", shape_params={"radius": 5})
    probe.set_device_channel_indices(np.arange(num_channels))
    probe.set_shank_ids(shank_ids)
    return probe
