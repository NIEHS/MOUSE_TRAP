# MOdular Unsupervised poSe Estimation and TRacking with behavioral Annotation and Prediction (MOUSE‑TRAP)

MOUSE‑TRAP is an application for:
- Converting files (videos, images, PDFs, DOCX, TXT) with live progress.

- Clipping videos to the exact frames you mark in a built-in annotator.

- Launching SLEAP Label or running SLEAP batch inference without the command line.

This package can be installed with:

```bash
pip install -e .
```

Then run the app from anywhere:

```bash
mouse-trap
```

Open the documentation with:

```powershell
start docs/_build/html/index.html # MacOS: open docs/_build/html/index.html
```

## Who uses this?

Developed for the Neurobehavioral Circuits Group (NBCG) under the guidance of Dr. Julieta Lischinsky. The NBCG studies the developmental and circuit mechanisms underlying social behaviors.


## Features

- **File Converter (GUI)**
  - **Video:** convert between `.mp4`, `.avi`, `.mov`, `.mkv`, `.gif`; transcode `.seq → .mp4/.avi`.
  - **Image:** convert common raster formats (`.jpg`, `.png`, `.tiff`, `.bmp`), and **image → PDF**.
  - **Documents:** **PDF ↔ DOCX/TXT** via Pandoc; **DOCX → PDF** via `docx2pdf`.
  - **Batching:** select multiple files or whole folders (with optional recursion + extension filter).
  - **Progress & logs:** live progress bar and streaming console output.

- **Annotation‑based Video Clipping**
  - Built‑in **Video Annotation** dialog to mark **enter/exit** frames per “intruder”.
  - Exports one clip per intruder (`<stem>_<Name>intruder.<ext>`), validates overlaps and order.
  - **CSV import** of annotations: `file_name` + any number of `<name>_in` / `<name>_out` columns.

- **SLEAP Integration (optional)**
  - **Launch SLEAP Label** from inside the app.
  - **Batch inference** helper for `sleap-nn track` with a guided form, logging, and “Skip OK” re‑runs.



## Prerequisites

- **Python:** 3.13+
- **Python deps:** installed automatically via `pip install -e .`  
  (`PyQt6`, `opencv-python`, `Pillow`, `pdf2image`, `pypandoc`, `docx2pdf`)
- **External tools:**
  - **FFmpeg** (required for most video conversions).
  - **Pandoc** (required for PDF/DOCX/TXT conversions via `pypandoc`).
  - **Poppler** (required by `pdf2image` for PDF → image).
  - **Microsoft Word** (Windows/macOS) if you want **DOCX → PDF** via `docx2pdf`.
- **Optional (for SLEAP features):**
  - A Conda env (e.g., `sleap`) with `sleap-label` and/or `sleap-nn` available on your `PATH`.

> **Tip:** If a conversion fails with an FFmpeg error, ensure `ffmpeg` runs in a terminal (`ffmpeg -version`).



## Installation

```bash
# optional, but recommended
python -m venv .venv
.venv\Scripts\activate  # MacOS: source .venv/bin/activate

pip install -e ".[dev,docs]"
```



## Quickstart

Launch the GUI:

```bash
mouse-trap
```

Typical workflows:

- **Convert files:** Select one or many files (or folders), choose **Output Format**, press **Convert**.
- **Clip by annotations:** Select a video, tick **Clip**, **Convert**, mark **Enter/Exit** in the dialog, **Done**.
- **SLEAP:** Use **Launch SLEAP** or **Run SLEAP Inference** to open the labeler or configure a batch `sleap-nn track` run.

> For step‑by‑step instructions, screenshots, and CSV examples, see **`docs/usage.rst`**.



## Development

Run tests and linters:

```bash
pytest -q
ruff check .
black .
```

Build the docs:

```bash
sphinx-build -b html docs docs/_build/html
```



## Project layout

```
├── src/
│   └── mouse_trap/
│       ├── __init__.py
│       ├── __main__.py        # entry point (installed script: `mouse-trap`)
│       ├── gui.py             # main window and workflows
│       ├── conversion.py      # conversions & worker thread
│       ├── annotation.py      # video annotation dialog
│       └── sleap_cli.py       # SLEAP batch dialog and helpers
├── docs/
└── tests/
```

## Contributors

- **Riley Harper**, National Institute of Environmental Health Sciences
