import math


def human_readable_size(size_bytes: int, binary: bool = False) -> str:
    """
    Convert a file size given in bytes to a human-readable format using division
    and remainder instead of iteration.

    Parameters
    ----------
    size_bytes : int
        The size in bytes.
    binary : bool, default=False
        If True, use binary prefixes (KiB, MiB, etc.). If False, use SI prefixes (KB, MB, etc.).

    Returns
    -------
    str
        A human-readable string representation of the size.

    Examples
    --------
    >>> human_readable_size(123)
    '123 B'
    >>> human_readable_size(1234, binary=True)
    '1.21 KiB'
    >>> human_readable_size(123456789)
    '123.46 MB'
    """
    # Check if size is negative
    if size_bytes < 0:
        raise ValueError("Size must be non-negative")

    if size_bytes == 0:
        return "0 B"

    # Define the suffixes for each size unit
    suffixes = ["", "K", "M", "G", "T", "P", "E", "Z", "Y"]

    # Calculate base and the exponent
    base = 1024 if binary else 1000
    exponent = int(math.log(size_bytes, base))

    if exponent == 0:
        return f"{size_bytes} B"

    # Calculate the human-readable size
    human_readable_value = size_bytes / (base**exponent)

    # Return formatted size with suffix
    return f"{human_readable_value:.2f} {suffixes[exponent]}{'i' if binary else ''}B"
