import re
from copy import copy
from glob import iglob
import os


def generate_regex_from_fstring(fstring_pattern: str):
    """
    Transform a string from reverse f-string format to a proper regex pattern.

    Parameters
    ----------
    fstring_pattern: str
        string pattern where the information to capture is in curly brackets.

    Returns
    -------
    str
        regex pattern

    Example
    -------

    >>> fstring_pattern = "sub-{subject_id}/sub-{subject_id}/ses-{session_id}"
    >>> pattern = generate_regex_from_fstring(fstring_pattern)
    >>> print(pattern)
    sub-(?P<subject_id>.+)/sub-(?P=subject_id)/ses-(?P<session_id>.+)

    >>> import re
    >>> re.match(pattern, "sub-001/sub-001/ses-abc")
    {'subject_id': '001', 'session_id': 'abc'}

    """
    # Find all group names in the filename pattern
    regex_groups = re.findall(r"{(\w+)}", fstring_pattern)

    # Replace each group name in the pattern with a named capture group pattern
    regex_pattern = copy(fstring_pattern)
    for group_name in set(regex_groups):
        regex_pattern = regex_pattern.replace("{" + group_name + "}", rf"(?P<{group_name}>.+)", 1)

    # Replace subsequent occurrences with reference to appropriate capture group pattern
    for group_name in set(regex_groups):
        regex_pattern = regex_pattern.replace("{" + group_name + "}", rf"(?P={group_name})")

    return regex_pattern


def glob_pattern(directory_path: str, pattern: str):
    """
    Take a directory and find all paths within that match a pattern.
    Also return the values for each of the groups

    Parameters
    ----------
    directory_path: str
    pattern: str

    Returns
    -------
    dict

    """
    out = dict()
    paths = iglob(os.path.join(directory_path, "**", "*"))
    for path in paths:
        path.replace("""\\""", """\\\\""")
        match = re.match(os.path.join(directory_path, pattern), path)
        if match:
            out[path] = match.groupdict()
    return out
