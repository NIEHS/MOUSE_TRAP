import os
import sys
from datetime import datetime

# Add src to sys.path so Sphinx can find the package without installing it
sys.path.insert(0, os.path.abspath('../src'))

project = 'MOUSE-TRAP'
author = 'Riley Harper'
copyright = f'{datetime.now().year}, {author}'
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx_autodoc_typehints',
]
templates_path = ['_templates']
exclude_patterns = []

# Use Furo if available, otherwise the default theme
html_theme = 'alabaster'
try:
    import furo  # noqa: F401
    html_theme = 'furo'
except Exception:
    pass
html_static_path = ['_static']
