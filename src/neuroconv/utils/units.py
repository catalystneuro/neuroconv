"""Helpers for physical units."""

import warnings


def get_conversion_from_unit(unit: str) -> float:
    """
    Get conversion (to Volt or Ampere) from unit in string format.

    Parameters
    ----------
    unit : str
        Unit as string. E.g. pA, mV, uV, etc...

    Returns
    -------
    float
        The conversion factor to convert to Ampere or Volt.
        For example, for 'pA' returns 1e-12 to convert to Ampere.
    """
    # Normalize: drop surrounding whitespace and fold the micro sign (U+00B5 'µ' and Greek mu U+03BC 'μ') to 'u',
    # so e.g. " µV " is recognized as micro-volts rather than falling through to the 1.0 warning.
    unit = (unit or "").strip().replace("µ", "u").replace("μ", "u")
    if unit in ["pA", "pV"]:
        conversion = 1e-12
    elif unit in ["nA", "nV"]:
        conversion = 1e-9
    elif unit in ["uA", "uV"]:
        conversion = 1e-6
    elif unit in ["mA", "mV"]:
        conversion = 1e-3
    elif unit in ["A", "V"]:
        conversion = 1.0
    else:
        conversion = 1.0
        warnings.warn("No valid units found for traces in the current file. Gain is set to 1, but this might be wrong.")
    return float(conversion)
