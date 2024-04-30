def human_readable_size(size_bytes: int) -> str:
    """
    Convert a file size given in bytes to a human-readable format.

    Parameters
    ----------
    size_bytes : int
        The size in bytes.

    Returns
    -------
    str
        A human-readable string representation of the size.

    Examples
    --------
    >>> human_readable_size(123)
    '123 B'
    >>> human_readable_size(1234)
    '1.21 KB'
    >>> human_readable_size(123456789)
    '117.74 MB'
    """
    # Check if size is negative
    if size_bytes < 0:
        raise ValueError("Size must be non-negative")

    # Define the suffixes for each size unit
    suffixes = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
    i = 0
    # Convert bytes to a float for division
    double_size = float(size_bytes)

    # Find the appropriate unit
    while double_size >= 1024 and i < len(suffixes) - 1:
        double_size /= 1024.
        i += 1

    # Format the size with 2 decimal places and the appropriate suffix
    return f"{double_size:.2f} {suffixes[i]}"
