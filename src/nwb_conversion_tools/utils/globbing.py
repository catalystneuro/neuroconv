"""Authors: Cody Baker."""
import re
from warnings import warn


def get_fstring_variable_names(fstring: str):
    """
    Extract and return all variable names from an fstring.

    A variable is defined as any expression inside curly brackets within the f-string.
    Also returns the separators, the strings remnants that surround the variables.

    Example
    -------
        variable_names, separators = get_fstring_variable_names(fstring="a/{x}b{y}/c{z}")
        variable_names = ["x", "y", "z"]
        separators = ["a/", "b", "/c"", ""]
    """
    matches = re.findall("{.*?}", fstring)  # {.*?} optionally matches any characters enclosed by curly brackets
    variable_names = [match.lstrip("{").rstrip("}") for match in matches]
    assert not any(
        (variable_name == "" for variable_name in variable_names)
    ), "Empty variable name detected in f-string! Please ensure there is text between all enclosing '{' and '}'."

    pattern = "^.*?{|}.*?{|}.*?$"
    # Description: patttern matches the all expressions outside of curly bracket enclosures
    #     .*?{   optionally matches any characters optionally before curly bracket opening
    #     |      logical 'or'
    #     }.*?{  between a curly bracket closure and opening
    #     |
    #     }.*?   after a closure
    separators = [x.rstrip("{").lstrip("}") for x in re.findall(pattern=pattern, string=fstring)]
    if any((separator == "" for separator in separators[1:-1])):
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
    pattern = "^" + "(.+)".join(separators) + "$"  # (.+) matches any non-empty sequence of characters
    pattern_match = re.findall(pattern=pattern, string=filename)
    assert pattern_match, "Unable to match f-string pattern to filename! Please double check both structures."
    variable_values = pattern_match[0]
    for idx in range(len(variable_values) - 1):
        assert (
            separators[idx + 1] not in variable_values[idx]
        ), "Adjacent variable values contain the separator character! The f-string is not invertible."
    results = dict()
    for variable_name, variable_value in zip(variable_names, variable_values):
        if variable_value != results.get(variable_name, variable_value):
            raise ValueError(
                f"Duplicated variable placements for '{variable_name}' in f-string do not match in instance! "
                f"Expected '{results[variable_name]}' but found '{variable_value}'."
            )
        results.update({variable_name: variable_value})
    return results
