"""Script to analyze docstrings of getter functions/methods in the neuroconv package."""

import ast
import os
from pathlib import Path
from typing import List, Tuple


def get_docstring(node: ast.FunctionDef) -> str:
    """
    Extract docstring from a function node.

    Parameters
    ----------
    node : ast.FunctionDef
        The AST node representing a function definition.

    Returns
    -------
    str
        The docstring of the function, or "No docstring" if none exists.
    """
    docstring_node = ast.get_docstring(node)
    return docstring_node if docstring_node else "No docstring"


def is_getter_function(node: ast.FunctionDef) -> bool:
    """
    Check if a function is a getter function (starts with 'get_').

    Parameters
    ----------
    node : ast.FunctionDef
        The AST node representing a function definition.

    Returns
    -------
    bool
        True if the function is a getter function, False otherwise.
    """
    return node.name.startswith("get_")


def get_class_methods(node: ast.ClassDef) -> dict:
    """
    Get all getter methods from a class definition.

    Parameters
    ----------
    node : ast.ClassDef
        The class definition node to analyze.

    Returns
    -------
    dict
        Dictionary mapping method names to their docstrings.
    """
    methods = {}
    for item in node.body:
        if isinstance(item, ast.FunctionDef) and is_getter_function(item):
            methods[item.name] = get_docstring(item)
    return methods


def analyze_file(file_path: Path, output_file) -> None:
    """
    Analyze getter functions in a Python file.

    Parameters
    ----------
    file_path : Path
        Path to the Python file to analyze.
    output_file : file object
        File to write the analysis results to.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
    except Exception as e:
        output_file.write(f"Error parsing {file_path}: {e}\n")
        return

    # First pass: collect all classes and their methods
    classes = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = get_class_methods(node)
            if methods:  # Only add classes that have getter methods
                classes[node.name] = methods

    # Second pass: handle standalone functions
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and is_getter_function(node):
            # Skip if this is a method we've already processed
            parent_class = next((class_name for class_name, methods in classes.items() 
                               if node.name in methods), None)
            if not parent_class:
                output_file.write(f"\nFunction: {node.name}\n")
                output_file.write("Docstring:\n")
                output_file.write(f"{get_docstring(node)}\n")
                output_file.write("-" * 80 + "\n")

    # Output class methods
    for class_name, methods in classes.items():
        for method_name, docstring in methods.items():
            output_file.write(f"\nFunction: {class_name}.{method_name}\n")
            output_file.write("Docstring:\n")
            output_file.write(f"{docstring}\n")
            output_file.write("-" * 80 + "\n")


def analyze_getter_functions(package_dir: Path, output_path: Path) -> None:
    """
    Analyze all getter functions in the package.

    Parameters
    ----------
    package_dir : Path
        Path to the package directory to analyze.
    output_path : Path
        Path to the output file where results will be written.
    """
    with open(output_path, "w", encoding="utf-8") as output_file:
        for file_path in package_dir.rglob("*.py"):
            if file_path.name.startswith("_"):  # Skip private modules
                continue
                
            output_file.write(f"\nAnalyzing {file_path}...\n")
            analyze_file(file_path, output_file)


def main():
    """Run the docstring analysis."""
    # Get the package directory (src/neuroconv)
    package_dir = Path(__file__).parent.parent
    output_path = package_dir / "tools" / "getter_docstrings_analysis.txt"
    analyze_getter_functions(package_dir, output_path)
    print(f"Analysis complete. Results written to: {output_path}")


if __name__ == "__main__":
    main()
