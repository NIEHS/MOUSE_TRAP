Developer Guide
===============

This document explains how to set up a development environment for MOUSE-TRAP,
run tests, build documentation, and use the linting/formatting tools.

Prerequisites
-------------

- Git
- Conda (Anaconda or Miniconda)
- Python 3.13 (used for development)
- System tools for the app itself:
  - FFmpeg on PATH
  - Poppler tools on PATH (for ``pdf2image``)
  - Pandoc installed (for ``pypandoc``)
  - Microsoft Word (on Windows) for ``docx2pdf``

Clone and environment setup
---------------------------

.. code-block:: bash

   # Clone the repo
   git clone https://github.com/NIEHS/MOUSE_TRAP.git
   cd MOUSE_TRAP

   # Create and activate a conda env
   conda create -n mouse_trap python=3.13
   conda activate mouse_trap

   # Install the package in editable mode with dev + docs extras
   pip install -e .[dev,docs]

Running the application
-----------------------

Once installed, the GUI can be started with:

.. code-block:: bash

   mouse-trap

This runs the ``mouse_trap.__main__:main`` entry point.

Linting and formatting
----------------------

This project uses:

- `black <https://black.readthedocs.io>`_ for formatting
- `ruff <https://docs.astral.sh/ruff/>`_ for linting

Configuration for both tools lives in ``pyproject.toml``.

To run them manually:

.. code-block:: bash

   # Format source and tests
   black src tests

   # Lint (and auto-fix where possible)
   ruff check src tests --fix

Pre-commit hooks
----------------

Pre-commit is configured in ``.pre-commit-config.yaml`` to run black and ruff
on each commit.

To set it up:

.. code-block:: bash

   pip install pre-commit
   pre-commit install
   pre-commit run --all-files  # optional one-time full run

After this, ``git commit`` will automatically format and lint staged files.

Running tests
-------------

Tests are written with ``pytest`` and live under ``tests/``.

.. code-block:: bash

   pytest        # run all tests
   pytest -v     # verbose output
   pytest tests/test_parse_status.py  # run a single test module

Building documentation
----------------------

Sphinx docs live in the ``docs/`` directory. To build the HTML docs:

.. code-block:: bash

   # From the repo root
   sphinx-build -b html docs docs/_build/html

Then open ``docs/_build/html/index.html`` in a browser.

Branching and workflow
----------------------

- Main development happens on the ``develop`` branch.
- Feature work should be done in topic branches (e.g. ``feature/new-dialog``)
  and merged via pull request.
- The ``main`` branch is reserved for stable releases.

Code layout
-----------

Source code lives under ``src/mouse_trap``:

- ``gui.py``: main PyQt application window and orchestration
- ``conversion.py``: conversion worker thread and helpers
- ``annotation.py``: video annotation dialog
- ``sleap_cli.py``: SLEAP batch GUI, CLI spec, and worker thread
- ``__main__.py``: CLI entry point for ``mouse-trap``

Tests are under ``tests/``, and documentation sources are under ``docs/``.
