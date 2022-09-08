import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

project = "NeuroConv"
copyright = "2022, CatalystNeuro"
author = "Cody Baker, Heberto Mayorquin, Szonja Weigl and Ben Dichter"

extensions = [
    "sphinx.ext.autodoc",  # Includes documentation from docstrings in docs/api
    "sphinx.ext.autosummary", # To-add
    "sphinx.ext.napoleon",  # Support for NumPy and Google style docstrings
    "sphinx_toggleprompt",  # Used to control >>> behavior in the conversion gallery example doctests
    "sphinx_copybutton",  # Used to control the copy button behavior in the conversion gallery doctsts
    "sphinx.ext.intersphinx",  # Allows links to other sphinx project documentation
    "sphinx_search.extension",  # Alows for auto search function the documentation
    "sphinx_design",  # Use for double column in the conversion gallery
    "myst_parser",  #  Allows to parse markdown (myst flavour)
    "sphinx.ext.viewcode",  # Shows source code in the documentation
]

myst_enable_extensions = ["colon_fence"]  # Suggested by sphinx_design for mynst to work well

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
autoclass_content = "both"
autodoc_member_order = "bysource"
autodata_content = "both"
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
}
