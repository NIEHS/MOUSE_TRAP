"""Sphinx configuration for the MOUSE-TRAP documentation."""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath("../src"))

project = "MOUSE-TRAP"
author = "Riley Harper"
copyright = f"{datetime.now().year}, {author}"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_autodoc_typehints",
]
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_attr_annotations = True
templates_path = ["_templates"]
exclude_patterns = []

html_theme = "alabaster"
try:

    html_theme = "furo"
except Exception:
    pass
