import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

project = "NeuroConv"
copyright = "2022, CatalystNeuro"
author = "Cody Baker and Ben Dichter"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "myst_parser",
    "sphinx_toggleprompt",
    "sphinx_copybutton",
    "sphinx.ext.intersphinx",
    "sphinx_search.extension",
    "sphinx.ext.viewcode",
    "sphinx.ext.extlinks",  # Allows to use shorter external links defined in the extlinks variable.
]

templates_path = ["_templates"]
master_doc = "index"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

# These paths are either relative to html_static_path
# or fully qualified paths (eg. https://...)
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
autodata_content = "both"  #
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "private-members": True,
    "show-inheritance": False,
    "toctree": True,
}
add_module_names = False

# Toggleprompt
toggleprompt_offset_right = 45  # This controls the position of the prompt (>>>) for the conversion gallery
toggleprompt_default_hidden = "true"

# Intersphinx
intersphinx_mapping = {
    "hdmf": ("https://hdmf.readthedocs.io/en/stable/", None),
    "pynwb": ("https://pynwb.readthedocs.io/en/stable/", None),
    "neuroconv": ("https://neuroconv.readthedocs.io/en/main/", None),
}

# To shorten external links
extlinks = {
    "pynwb": ("https://pynwb.readthedocs.io/en/stable/%s", ""),
    "nwbinspector": ("https://nwbinspector.readthedocs.io/en/dev/%s", ""),
}
