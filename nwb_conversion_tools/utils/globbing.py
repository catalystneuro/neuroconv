"""Authors: Cody Baker."""
import re
from warnings import warn


def get_fstring_variable_names(fstring: str):
    """
    Extract and return all variable names from an fstring.

    Also returns the separators, the strings remnants that surround the variables.

    Example
    -------
        variable_names, separators = get_fstring_variable_names(fstring="a/{x}b{y}/c{z}")
        variable_names = ["x", "y", "z"]
        separators = ["a/", "b", "/c"", ""]
    """
    matches = re.findall("{.*?}", fstring)
    variable_names = [match.lstrip("{").rstrip("}") for match in matches]
    assert not any(
        (variable_name == "" for variable_name in variable_names)
    ), "Empty variable name detected in f-string! Please ensure there is text between all enclosing '{' and '}'."
    separators = [x.rstrip("{").lstrip("}") for x in re.findall(pattern="^.*?{|}.*?{|}.*?$", string=fstring)]
    if separators[0] == "":
        separators = separators[1:]
    if separators[-1] == "":
        separators = separators[:-1]
    if any((separator == "" for separator in separators)):
        warn("There is an empty separator between two variables in the f-string! The f-string will not be invertible.")
    return variable_names, separators


def get_fstring_values_from_filename(filename: str, fstring: str):
    """
    Given a filename and an f-string rule, extract the values of the variables specified by the fs-tring.

    Parameters
    ----------
    filename : str
        String part of a file path, that is, prior to any suffixes.
        This is easily found aplpying `pathlib.Path(file_path).stem` to any file_path string.
    fstring : str
        String containing non-empty substrings enclosed by "{" and "}".
        These correspond to the names of variables thought to encode the actual filename string.
    """
    variable_names, separators = get_fstring_variable_names(fstring=fstring)
    pattern = "^"
    for separator in separators:
        pattern += f"{separator}(.+)"
    pattern += "$"
    variable_values = re.findall(pattern=pattern, string=filename)[0]
    return {variable_name: variable_value for variable_name, variable_value in zip(variable_names, variable_values)}
