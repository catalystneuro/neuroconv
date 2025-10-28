import inspect
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
html_theme = "pydata_sphinx_theme"
html_static_path = ["_static"]

# The name of an image file (within the static path) to use as favicon of the
# docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
html_favicon = "_static/favicon.ico"

# These paths are either relative to html_static_path or fully qualified paths (eg. https://...)
html_css_files = [
    "css/custom.css",
    "css/neuroconv_assistant.css",
]

html_js_files = [
    "js/neuroconv_assistant.js",
]


html_context = {
    # "github_url": "https://github.com", # or your GitHub Enterprise site
    "github_user": "catalystneuro",
    "github_repo": "neuroconv",
    "github_version": "main",
    "doc_path": "docs",
}


# Configure version switcher for documentation
# READTHEDOCS_VERSION_NAME is automatically set by ReadTheDocs during builds
# Documentation: https://docs.readthedocs.com/platform/stable/reference/environment-variables.html
# Possible values: "stable", "main", PR numbers like "1483", branch names like "feature/xyz"
version_match = os.environ.get("READTHEDOCS_VERSION_NAME", "stable")

html_theme_options = {
    "use_edit_page_button": True,
    "navbar_end": ["version-switcher", "navbar-icon-links"],  # Version switcher in navbar like NumPy/SciPy
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/catalystneuro/neuroconv",
            "icon": "fa-brands fa-github",
            "type": "fontawesome",
        },
    ],
    "switcher": {
        "json_url": "_static/switcher.json",
        "version_match": version_match,
    }
}

# Prevent Sphinx from prefixing class and function names with their module paths
# For example, displays 'ClassName' instead of 'package.module.ClassName'
add_module_names = False

# Add here link checks that should be ignored by the link checker action
linkcheck_anchors = False
linkcheck_ignore = [
    "https://buzsakilab.com/wp/",  # Ignoring because their ssl certificate is expired
    r"https://stackoverflow\.com/.*",  # The r is because of the regex, stackoverflow links are forbidden to bots
    "https://catalystneuro.com/*/",
    "https://doi.org/10.25080/cehj4257",  # Does not seem to support multiple access
]

# --------------------------------------------------
# Extension configuration
# --------------------------------------------------

# Napoleon
napoleon_google_docstring = False          # Disable support for Google-style docstrings (use NumPy-style instead)
napoleon_numpy_docstring = True            # Enable support for NumPy-style docstrings
napoleon_use_param = False                 # Do not convert :param: sections into Parameters; leave as-is
napoleon_use_ivar = True                   # Interpret instance variables as documented with :ivar:

# Autodoc
autoclass_content = "both"  # Concatenates docstring of the class with that of its __init__

autodoc_default_options = {
    "members": True,  # Enables automatic documentation of methods, attributes etc, not just the class docstring
    "member-order": "bysource", # Displays classes and methods by their order in source code
    "private-members": False,   # Do not include private members (those starting with an underscore)
    "undoc-members": True,      # Document members without docstrings, including class attributes
    "show-inheritance": False,
    "toctree": True,
    "exclude-members": "__new__",  # Do not display __new__ method in the docs
}



# Toggleprompt
toggleprompt_offset_right = 45  # This controls the position of the prompt (>>>) for the conversion gallery
toggleprompt_default_hidden = "true"

# Copybutton
copybutton_exclude = '.linenos, .gp'  # This avoids copying prompt (>>>) in the conversion gallery (issue #1465)


# Intersphinx
intersphinx_mapping = {
    "hdmf": ("https://hdmf.readthedocs.io/en/stable/", None),
    "pynwb": ("https://pynwb.readthedocs.io/en/stable/", None),
    "spikeinterface": ("https://spikeinterface.readthedocs.io/en/latest/", None),
    "nwbinspector": ("https://nwbinspector.readthedocs.io/en/dev/", None),
}

# --------------------------------------------------
# Custom Sphinx event handlers and setup
# --------------------------------------------------

def _correct_signatures(app, what, name, obj, options, signature, return_annotation):
    """Remove self from the signature of class methods."""
    if what == "class":
        signature = str(inspect.signature(obj.__init__)).replace("self, ", "")
    return (signature, return_annotation)


def update_version_switcher_in_read_the_docs(app, config):
    """Update switcher.json for ReadTheDocs PR/branch builds.

    Only runs on ReadTheDocs when building PR or branch versions.
    Modifies switcher.json directly since RTD uses the checked-out version.
    """

    # Only run on ReadTheDocs
    is_read_the_docs_build = bool(os.environ.get("READTHEDOCS"))
    if not is_read_the_docs_build:
        return

    # Get the ReadTheDocs version and canonical URL
    rtd_version = os.environ.get("READTHEDOCS_VERSION")

    # Only update for PR/branch builds (not stable or main)
    if rtd_version in ["stable", "main"]:
        return

    switcher_path = Path(app.srcdir) / "_static" / "switcher.json"


    # Create entry for current PR/branch
    # For PR builds, rtd_version is just the number (e.g., "1483")
    display_name = f"PR {rtd_version} build"
    entry_to_add = {
        "name": display_name,
        "version": rtd_version,
        "url":  os.environ.get("READTHEDOCS_CANONICAL_URL")
    }

    # Update switcher.json with PR/branch entry
    # switcher.json structure: [{"name": str, "version": str, "url": str}, ...]
    with open(switcher_path, "r") as f:
        switcher_entries = json.load(f)

    # Avoid duplicated entries
    version_exists = any(entry["version"] == rtd_version for entry in switcher_entries)
    if version_exists:
        return  # Entry already present, no update needed

    # Add and save new entry
    switcher_entries.append(entry_to_add)
    with open(switcher_path, "w") as f:
        json.dump(switcher_entries, f, indent=4)




def setup(app):
    """Register Sphinx event handlers."""
    # Connect signature correction for API docs
    app.connect("autodoc-process-signature", _correct_signatures)

    # Connect switcher.json updater for ReadTheDocs PR/branch builds
    app.connect("config-inited", update_version_switcher_in_read_the_docs)
