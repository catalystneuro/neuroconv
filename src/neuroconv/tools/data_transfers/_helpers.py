"""Collection of helper functions for assessing automated data transfers."""


def estimate_total_conversion_runtime(
    total_mb: float,
    transfer_rate_mb: float = 20.0,
    conversion_rate_mb: float = 17.0,
    upload_rate_mb: float = 40,
    compression_ratio: float = 1.7,
):
    """
    Estimate how long the combined process of data transfer, conversion, and upload is expected to take.

    Parameters
    ----------
    total_mb: float
        The total amount of data (in MB) that will be transferred, converted, and uploaded to dandi.
    transfer_rate_mb : float, default: 20.0
        Estimate of the transfer rate for the data.
    conversion_rate_mb : float, default: 17.0
        Estimate of the conversion rate for the data. Can vary widely depending on conversion options and type of data.
        Figure of 17MB/s is based on extensive compression of high-volume, high-resolution ecephys.
    upload_rate_mb : float, default: 40.0
        Estimate of the upload rate of a single file to the DANDI archive.
    compression_ratio : float, default: 1.7
        Estimate of the final average compression ratio for datasets in the file. Can vary widely.
    """
    c = 1 / compression_ratio  # compressed_size = total_size * c
    return total_mb * (1 / transfer_rate_mb + 1 / conversion_rate_mb + c / upload_rate_mb)
