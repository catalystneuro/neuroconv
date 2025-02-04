import subprocess
from pydantic import DirectoryPath, FilePath
import yaml

def get_all_docstrings(folder_path: DirectoryPath):
    """Get docstrings from all the getter functions ('get_*') in a specified directory.
    
    Parameters
    ----------
    folder_path : DirectoryPath
    The path to the directory containing the getter functions.
    
    Returns
    -------
    list
    A list of docstrings from the getter functions.
    """
    args = ["grep", "-r", "-n", "def get_", str(folder_path), "--exclude=getter_benchmark.py"]
    output = subprocess.run(args, capture_output=True, text=True)
    docstrings = []
    for line in output.stdout.split("\n"):
        split_line = line.split(":")
        if len(split_line) < 3:
            continue
        file_path, line_number = split_line[:2]
        line = ":".join(split_line[2:])
        signature_line_index = int(line_number) - 1
        docstring_line_index = get_docstring_line_index(file_path=file_path, line_index=signature_line_index)
        docstring = get_docstring(file_path=file_path, line_index=docstring_line_index)
        docstrings.append(docstring)
    return docstrings

def get_docstring_line_index(file_path: FilePath, line_index: int):
    """
    Find the line index where a docstring should start in a Python file.

    Parameters
    ----------
    file_path : FilePath
        Path to the Python file to analyze
    line_index : int
        Line index in the file where the function/class definition starts

    Returns
    -------
    int
        The line index where the docstring should begin, accounting for multi-line function signatures

    Notes
    -----
    This function handles both single-line and multi-line function/class signatures.
    For multi-line signatures, it looks for the line ending with ':' to determine where
    the function/class body begins.
    """
    with open(file_path, "r") as file:
        lines = file.read().splitlines()
    first_line = lines[line_index]
    has_multiline_signature = first_line.strip().endswith("(")
    while has_multiline_signature:
        line_index += 1
        has_multiline_signature = not(lines[line_index].strip().endswith(":"))
    return line_index + 1

def get_docstring(file_path: FilePath, line_index: int):
    """Extract docstring from a Python file given a line index.

    Parameters
    ----------
    file_path : FilePath
        Path to the Python file to read from.
    line_index : int
        Line number where the docstring begins.

    Returns
    -------
    str or None
        If a docstring is found, returns the complete docstring including quotes.
        Returns None if no docstring is found at the given line.
    """
    with open(file_path, "r") as file:
        lines = file.read().splitlines()
        
    first_line = lines[line_index]
    has_docstring = first_line.strip().startswith('"""')
    if not has_docstring:
        return None
    
    is_single_line_docstring = first_line.count('"""') == 2
    if is_single_line_docstring:
        return first_line
    
    docstring_lines = [first_line]
    is_last_line = False
    line_index = line_index
    while not(is_last_line):
        line_index += 1
        line = lines[line_index]
        docstring_lines.append(line)
        is_last_line = line.strip().endswith('"""')
    docstring = "\n".join(docstring_lines)
    return docstring

def has_returns_section(docstring: str | None):
    """Check if a docstring contains a numpydoc style 'Returns' section.

    Parameters
    ----------
    docstring : str
        The docstring to check for a 'Returns' section.

    Returns
    -------
    bool
        True if the docstring contains a numpydoc style 'Returns' section, False otherwise.
    """
    if docstring is None:
        return False
    split_docstring = docstring.split("\n")
    for idx, line in enumerate(split_docstring):
        if line.strip() == "Returns" and split_docstring[idx + 1].strip() == "-------":
            return True
    return False


def main():
    folder_path = "/Users/pauladkisson/Documents/CatalystNeuro/Neuroconv/neuroconv"
    gt_path = "/Users/pauladkisson/Documents/CatalystNeuro/Neuroconv/neuroconv/getter_benchmark_gt.yaml"
    save_gt = True

    docstrings = get_all_docstrings(folder_path=folder_path)
    getter_has_docstring, getter_has_docstring_with_returns_section = [], []
    for docstring in docstrings:
        getter_has_docstring.append(docstring is not None)
        getter_has_docstring_with_returns_section.append(has_returns_section(docstring=docstring))

    if save_gt:
        with open(gt_path, "w") as f:
            gt = dict(gt=getter_has_docstring)
            yaml.dump(gt, f)
    with open(gt_path, "r") as f:
        gt = yaml.safe_load(f)

    from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
    off_target_confusion = confusion_matrix(gt["gt"], getter_has_docstring)
    on_target_confusion = confusion_matrix(gt["gt"], getter_has_docstring_with_returns_section)
    import matplotlib.pyplot as plt
    disp = ConfusionMatrixDisplay(confusion_matrix=off_target_confusion)
    disp.plot()
    plt.show()
    disp = ConfusionMatrixDisplay(confusion_matrix=on_target_confusion)
    disp.plot()
    plt.show()
    

if __name__ == "__main__":
    main()