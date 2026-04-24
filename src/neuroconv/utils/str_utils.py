import math


def to_camel_case(name: str) -> str:
    """Convert a string with underscores or hyphens to CamelCase.

    Preserves all-uppercase acronyms and capitalizes other parts.

    Parameters
    ----------
    name : str
        String with underscores or hyphens to convert.

    Returns
    -------
    str
        CamelCase version of the input string.

    Examples
    --------
    >>> to_camel_case("ACC_miniscope2")
    'ACCMiniscope2'
    >>> to_camel_case("HPC_miniscope1")
    'HPCMiniscope1'
    >>> to_camel_case("simple_name")
    'SimpleName'
    >>> to_camel_case("my-device-name")
    'MyDeviceName'
    """
    parts = name.replace("-", "_").split("_")
    camel_parts = []
    for part in parts:
        # If the part is all uppercase (like ACC, HPC), keep it as-is
        # Otherwise, capitalize it
        if part.isupper():
            camel_parts.append(part)
        else:
            camel_parts.append(part.capitalize())
    return "".join(camel_parts)


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
