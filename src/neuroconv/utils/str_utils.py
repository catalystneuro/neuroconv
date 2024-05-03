def human_readable_size(size_bytes: int, binary=True) -> str:
    """
    Convert a file size given in bytes to a human-readable format.

    Parameters
    ----------
    size_bytes : int
        The size in bytes.
    binary : bool, optional
        If True, use binary prefixes (KiB, MiB, etc.). If False, use SI prefixes

    Returns
    -------
    str
        A human-readable string representation of the size.

    Examples
    --------
    >>> human_readable_size(123)
    '123 B'
    >>> human_readable_size(1234)
    '1.21 KiB'
    >>> human_readable_size(123456789, binary=False)
    '123.46 MB'
    """
    # Check if size is negative
    if size_bytes < 0:
        raise ValueError("Size must be non-negative")

    # Define the suffixes for each size unit
    suffixes = ["", "K", "M", "G", "T", "P", "E", "Z", "Y"]
    i = 0
    # Convert bytes to a float for division
    size_float = float(size_bytes)

    base = 1000 if not binary else 1024

    # Find the appropriate unit
    while size_float >= base and i < len(suffixes) - 1:
        size_float /= base
        i += 1

    if not i:
        return f"{size_bytes} B"

    # Format the size with 2 decimal places and the appropriate suffix
    return f"{size_float:.2f} {suffixes[i]}{'i' if binary else ''}B"
