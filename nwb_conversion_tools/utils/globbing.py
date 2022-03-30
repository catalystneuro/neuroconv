"""Authors: Cody Baker."""
import re


def get_fstring_variable_names(fstring: str):
    """
    Extract and return all variable names from an fstring.

    Example: get_fstring_variable_names(fstring="a/{x}b{y}/c{z}") = ["x", "y", "z"]
    """
    matches = re.findall("{.*?}", fstring)
    variable_names = [match.lstrip("{").rstrip("}") for match in matches]
    assert not any(
        (variable_name == "" for variable_name in variable_names)
    ), "Empty variable name detected in f-string! Please ensure there is text between all enclosing '{' and '}'."
    return variable_names


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
    variable_names = get_fstring_variable_names(fstring=fstring)
    husk = [x.rstrip("{").lstrip("}") for x in re.findall("^.*?{|}.*?{|}.*?$")]
    variable_values = filename
    return {variable_name: variable_value for variable_name, variable_value in zip(variable_names, variable_values)}
