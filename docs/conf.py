import os
import sys
sys.path.insert(0, os.path.abspath('../src'))

project = 'SlyAPI for Python'
copyright = '2023, Dunkyl 🔣🔣'
author = 'Dunkyl 🔣🔣'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'myst_parser',
    'sphinxcontrib_trio',
    'sphinx_copybutton',
    'sphinxext.opengraph',
    "sphinx.ext.intersphinx",
    'sphinx.ext.autodoc',
    'sphinx.ext.duration',
    'sphinx.ext.autosummary',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.coverage',
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "aiohttp": ("https://docs.aiohttp.org/en/stable/", None),
}

napoleon_use_rtype = False
napoleon_numpy_docstring = False
napoleon_preprocess_types = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True

autoclass_content = "both"
autosummary_generate = True
numpydoc_show_class_members = False

myst_heading_anchors = 3

autodoc_default_options = { # type: ignore
    "members": True,
    "inherited-members": False,
    "private-members": False,
    "show-inheritance": True,
    "undoc-members": True,
    "member-order": "bysource",
    "special-members": "__await__",
}

autodoc_member_order = 'bysource'
autodoc_typehints = "description"
# autodoc_class_signature = "separated"

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']


# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'furo'


html_title = 'SlyAPI for Python'
html_favicon = 'Sly Logo py.svg'
html_logo = html_favicon

html_theme_options = {
    "source_repository": "https://github.com/dunkyl/SlyAPI-Python/",
    "source_branch": "main",
    "source_directory": "docs/",
}

ogp_social_cards = {
    "enable": False
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

html_js_files = [ 'js/custom.js', ]

html_css_files = [ 'css/custom.css', ]

def env_get_outdated(app, env, added, changed, removed): # type: ignore
    return ['index']

def setup(app): # type: ignore
    app.connect('env-get-outdated', env_get_outdated) # type: ignore