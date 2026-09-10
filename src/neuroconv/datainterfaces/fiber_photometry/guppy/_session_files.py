"""Recognizing GuPPy's file conventions inside a session folder.

Shared by the acquisition formats whose sessions hold a mix of files: Doric and NPM both have to tell
an acquisition file from an event file by inspection, because GuPPy identifies neither by name.
"""


def is_event_csv(file_path) -> bool:
    """Return whether a ``.csv`` holds GuPPy event onsets rather than acquisition traces.

    A GuPPy event CSV is a lone ``timestamps`` column. Doric exports are wide and lead with a device
    header row, so the two are told apart by the header alone -- the same distinction GuPPy draws when
    it decides which files in a session folder its Doric reader should look at.

    Parameters
    ----------
    file_path : FilePath
        Path to the ``.csv`` to inspect. Only its header row is read.

    Returns
    -------
    bool
        Whether the file is a GuPPy event CSV.
    """
    import pandas

    columns = list(pandas.read_csv(file_path, nrows=0).columns)
    return len(columns) == 1 and str(columns[0]).strip().lower() == "timestamps"
