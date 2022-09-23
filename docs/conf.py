import sys
import inspect
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from neuroconv.tools import spikeinterface
from neuroconv.tools import roiextractors

project = "NeuroConv"
copyright = "2022, CatalystNeuro"
author = "Cody Baker, Heberto Mayorquin, Szonja Weigl and Ben Dichter"

extensions = [
    "sphinx.ext.napoleon",  # Support for NumPy and Google style docstrings
    "sphinx.ext.autodoc",  # Includes documentation from docstrings in docs/api
    "sphinx.ext.autosummary",  # Not clear. Please add if you know
    "sphinx_toggleprompt",  # Used to control >>> behavior in the conversion gallery example doctests
    "sphinx_copybutton",  # Used to control the copy button behavior in the conversion gallery doctests
    "sphinx.ext.intersphinx",  # Allows links to other sphinx project documentation sites
    "sphinx_search.extension",  # Allows for auto search function the documentation
    "sphinx.ext.viewcode",  # Shows source code in the documentation
    "sphinx.ext.extlinks",  # Allows to use shorter external links defined in the extlinks variable.
]

templates_path = ["_templates"]
master_doc = "index"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

# These paths are either relative to html_static_path or fully qualified paths (eg. https://...)
html_css_files = [
    "css/custom.css",
]

html_theme_options = {
    "collapse_navigation": False,
}

# --------------------------------------------------
# Extension configuration
# --------------------------------------------------

# Napoleon
napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_use_param = False
napoleon_use_ivar = True
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = True
napoleon_include_special_with_doc = True

# Autodoc
autoclass_content = "both"  # Concatenates docstring of the class with that of its __init__
autodoc_member_order = "bysource"  # Displays classes and methods by their order in source code
autodata_content = "both"
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "private-members": True,
    "show-inheritance": False,
    "toctree": True,
}
add_module_names = False


def _correct_signatures(app, what, name, obj, options, signature, return_annotation):
    if what == "class":
        signature = str(inspect.signature(obj.__init__)).replace("self, ", "")
    return (signature, return_annotation)


def setup(app):  # This makes the data-interfaces signatures display on the docs/api, they don't otherwise
    app.connect("autodoc-process-signature", _correct_signatures)


# Toggleprompt
toggleprompt_offset_right = 45  # This controls the position of the prompt (>>>) for the conversion gallery
toggleprompt_default_hidden = "true"

# Intersphinx
intersphinx_mapping = {
    "hdmf": ("https://hdmf.readthedocs.io/en/stable/", None),
    "pynwb": ("https://pynwb.readthedocs.io/en/stable/", None),
    "spikeinterface": ("https://spikeinterface.readthedocs.io/en/latest/", None),
}

# To shorten external links
extlinks = {
    "nwbinspector": ("https://nwbinspector.readthedocs.io/en/dev/%s", ""),
}
