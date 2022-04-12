"""Authors: Cody Baker."""
import re
from typing import List
from warnings import warn


def decompose_f_string(f_string: str) -> (List[str], List[str]):
    """
    Decompose an f-string into the list of variable names and the separators between them.

    An f-string is any string that contains enclosed curly brackets around text.
    A variable is defined as the text expression within the enclosed curly brackets.
    The separators are the strings remnants that surround the variables.

    An example f-string and components would be: 'This is {an} f-string!', with variable 'an' and separators
    'This is ' and ' f-string!'.
    An instance of this example would be: 'This is definetely a good f-string!' with variable value 'definetely a good'.

    Example
    -------
        variable_names, separators = decompose_f_string(f_string="a/{x}b{y}/c{z}")
        # variable_names = ["x", "y", "z"]
        # separators = ["a/", "b", "/c"", ""]
    """
    matches = re.findall("{.*?}", f_string)  # {.*?} optionally matches any characters enclosed by curly brackets
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
    separators = [x.rstrip("{").lstrip("}") for x in re.findall(pattern=pattern, string=f_string)]
    if any((separator == "" for separator in separators[1:-1])):
        warn(
            "There is an empty separator between two variables in the f-string! "
            "The f-string will not be uniquely invertible."
        )
    return variable_names, separators


def parse_f_string(string: str, f_string: str):
    """
    Given an instance of an f-string rule, extract the values of the variables specified by the f-string.

    Recovery of values is only possible in cases where the string instance is uniquely invertible,
    which requires at a minumum requires...
        1) Separators between all curly bracket enclosures, *e.g.*, '{var1}{var2}' is not allowed.
           An easy way to resolve this is to add a unique separator between them, *i.e.*, '{var1}-{var2}'.
        2) The separator character(s) cannot also occur within the variable values, *e.g.*, '{var1}b{var2}' on
           instance 'sub_01bsess_040122' where var1='sub_01 and' and var2='sess_040122'. Since the separator is a single
           character 'b' which also occurs in the instance of var1, it cannot be determined which occurence is the
           proper separator.

           Resolving this relies on choosing unique separators between variables in the f-string rule; either a single
           character that you know will never occur in any of your instances, or preferably a sequence of characters
           that would not occur together. In the example above, a simple separator of '-' would suffice, but if other
           instances might include that, such as var1='sub-05', then a sequential separator of '--' would work instead.

    Parameters
    ----------
    string : str
        An instance of the f-string rule.
    fstring : str
        String containing non-empty substrings enclosed by "{" and "}".
        These correspond to the names of variables thought to encode the actual filename string.
    """
    variable_names, separators = decompose_f_string(f_string=f_string)
    pattern = "^" + "(.+)".join(separators) + "$"  # (.+) matches any non-empty sequence of characters
    pattern_match = re.findall(pattern=pattern, string=string)
    assert pattern_match, "Unable to match f-string pattern to string! Please double check both structures."
    variable_values = pattern_match[0]
    for idx in range(len(variable_values) - 1):
        assert (
            separators[idx + 1] not in variable_values[idx]
        ), "Adjacent variable values contain the separator character! The f-string is not uniquely invertible."
    values = dict()
    for variable_name, variable_value in zip(variable_names, variable_values):
        if variable_value != values.get(variable_name, variable_value):
            raise ValueError(
                f"Duplicated variable placements for '{variable_name}' in f-string do not match in instance! "
                f"Expected '{values[variable_name]}' but found '{variable_value}'."
            )
        values.update({variable_name: variable_value})
    return values
