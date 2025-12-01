Usage
=============

* **Converting files** (videos, images, PDFs, DOCX, TXT) with live progress.
* **Clipping videos** to the exact frames you mark in a built-in annotator.
* **Launching SLEAP Label** or **running SLEAP batch inference** without the command line.

Who is this for?
----------------
Neurobiology researchers who would like an an application that contains integration for end-to-end unsupervised behavior segmentation.

Before you begin
----------------

**Requirements**

* Python 3.13
* FFmpeg on your system ``PATH`` (needed for most video conversions).
* Pandoc for certain PDF/DOCX/TXT conversions used via ``pypandoc``.
* Microsoft Word (Windows/macOS) if you plan to use ``DOCX → PDF`` via ``docx2pdf``.
* (Optional) **SLEAP** in a Conda environment named ``sleap`` if you plan to label or run inference.

.. tip::

   If a conversion fails with “FFmpeg error …”, install FFmpeg and make sure running
   ``ffmpeg`` in a terminal works on your machine.

Install and launch
------------------

From your project root:

1) Install the app:

   .. code-block:: bash

      pip install -e .

   This installs the package and allows it to easily be run in the future with :code:`mouse-trap`.

2) Launch the GUI:

   .. code-block:: bash

      mouse-trap

   This runs the package entry point and opens the main window.

A quick tour of the main window
-------------------------------

**File selection row**:

* **Select File**: choose one file.
* **Select Multiple Files** + **Select File**: multi-select many files at once.
* **Select Input Folder**: pick one or more folders, optionally **Include subfolders**,
  and filter by extension (e.g., ``.mp4``) to queue many files.

**Options row**:

* **Select Output Folder** (and **Choose Folder**): send results to a specific location
  instead of the same directory as the inputs.
* **Output Format**: a drop-down that allows you to choose from a set of valid outputs for the current input type.

**Analysis & automation row**:

* **Clip** - export only named intervals you annotate.
* **Import CSV Annotations** - load *enter/exit* frames from a CSV.
* **Launch SLEAP** - start SLEAP Label (auto-detect PATH/Conda).
* **Run SLEAP Inference** - batch :code:`sleap-nn track` with a guided form and logging.

**Run section**:

* **Convert** - start the job(s). For multi-file queues you can opt to be prompted on each file if you'd like to process that file or not.
* **Progress bar** and **console** - live status and tool output.

Common tasks (step-by-step)
---------------------------

Convert a single file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Click **Select File** and choose your file.
2. Pick an **Output Format**.
3. (Optional) Check **Select Output Folder** and click **Choose Folder**.
4. Click **Convert** and watch the progress bar/console.

Convert many files at once
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Option 1: multi-select**

1. Check **Select Multiple Files**, then click **Select File** and multi-select.  
2. Choose **Output Format** → **Convert**.  
3. When asked “Do you want to be prompted on every file?”, choose **Yes** to approve
   each file or **No** to process all selected files.

**Option 2: whole folder(s)**

1. Click **Select Input Folder**.
2. In the dialog, select one or more folders.
3. When prompted for **File Type Filter**, enter the extension to include (e.g., ``.avi``).
4. (Optional) Check **Include subfolders** to recurse.
5. Choose **Output Format** → **Convert**.

Export each PDF page as an image
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Select a ``.pdf`` file.
2. Set **Output Format** to an image type (e.g., ``.png``).
3. Click **Convert**. Each page is written as ``<stem>_page0.png``, ``_page1.png``, etc.

Convert documents and text
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* **PDF → DOCX** or **PDF → TXT** uses Pandoc via ``pypandoc``.
* **DOCX → PDF** uses ``docx2pdf`` (Word required on Windows/macOS).
* **TXT ↔ DOCX/PDF** uses Pandoc via ``pypandoc``.

Video clipping by enter/exit frames
-----------------------------------

Clipping exports only the portions of a video where an intruder is present between the enter and exit frames you mark. Supported inputs are ``.seq``, ``.mp4``, or ``.avi``.

Workflow
~~~~~~~~~~~~~~~~~~~~

1. Select your video and choose a output format (e.g., ``.mp4``).
2. Check **Clip**, then click **Convert**.

   *If the input is ``.seq`` or ``.mp4``, the app first creates a temporary MJPEG
   ``.avi`` for precise frame scrubbing; if the input is ``.avi``, it is used directly.*

3. In **Video Annotation**:

   * **Play/Pause**, drag the **slider**, and choose a **Scrub Step** (1/10/100/1000 frames).
   * Click **Mark Enter** → type a short name (e.g., ````).
   * Click **Mark Exit** → pick that name (or type it) to set its exit frame.
   * **Table editing:** double-click numbers to edit; **single-click** an Enter/Exit cell to
     jump to that frame; **right-click** a row to **Duplicate** or **Delete**; **Delete** key
     removes selected rows. The **Frame** label starts at 1 and updates as you scrub.

4. Click **Done** to return and write clips. Outputs are named:

   ``<video_stem>_<IntruderName>intruder<ext>`` (one file per intruder).

* Each intruder must have both **enter** and **exit**, with **exit ≥ enter**.
* Intervals for different intruders **must not overlap**; fix overlaps before saving.

Load annotations from CSV (batch-friendly)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use a CSV with a header ``file_name`` and any number of ``<name>_in`` / ``<name>_out`` pairs:

.. code-block:: csv

   file_name,Alice_in,Alice_out,Bob_in,Bob_out
   trial01.mp4,120,420,,-     # Bob missing → ignored
   trial02.avi,, ,350,610     # Alice missing → ignored, Bob used

* The app validates the header and loads non-empty pairs.

Using SLEAP from the GUI
------------------------

Launch SLEAP Label (the SLEAP GUI)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Click **Launch SLEAP**. The app tries, in order:

1. **Environment variable** ``SLEAP_LABEL`` if it points to ``sleap-label``.
2. **System PATH** for ``sleap-label``.
3. **Conda**: ``conda run -n sleap sleap-label`` using an auto-detected ``conda``. On Windows,
   this may run via ``cmd.exe /c``. If SLEAP fails to start, an error dialog advises checking
   your PATH/Conda setup.
Run SLEAP batch inference (``sleap-nn track``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Click **Run SLEAP Inference** to open a guided dialog:

* **Videos folder** - root directory containing your videos.
* **Predictions folder** - where ``.predictions.slp`` outputs go.
* **Log file** - a tab-separated log; check **Skip items with latest status = OK** to
  avoid recomputing successes on re-runs.
* **Include subfolders** - recurse into subdirectories (skips any ``*_frames`` directories).

CLI options are organized into tabs (**Essential**, **Model**, **Image**, **Data**,
**Performance**, **Tracking**) mirroring SLEAP’s CLI. Defaults are provided, with tooltips
for each flag.

What happens under the hood
~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Videos are discovered (respecting your recursion setting; ``*_frames`` folders are skipped).
* Output paths are built like: ``<predictions>/<relative path sanitized>.predictions.slp``.
* The exact CLI is assembled for each video. If ``sleap-nn`` is not on PATH, the app falls
  back to ``conda run -n sleap sleap-nn track ...``. Output is streamed line-by-line to the
  console; progress updates appear in the GUI. Results are logged as **OK** or **FAIL**.

Keyboard & interaction (Annotation dialog)
------------------------------------------

* **Space / Play** - toggle playback.
* **Left/Right Arrow** - scrub by the selected **Scrub Step**.
* **Single-click** an Enter/Exit **cell** - jump to that frame.
* **Double-click** Enter/Exit **cell** - edit the number.
* **Right-click** row - **Duplicate** or **Delete**.
* **Delete** key - remove selected rows.
* **Frame numbers start at 1**.

Supported input → output formats
--------------------------------

The **Output Format** menu is filtered from this mapping:

=================  ================================================
Input type         Allowed outputs (choose from the drop-down)
=================  ================================================
``.seq``           ``.mp4``, ``.avi``
Video (``.mp4``,   ``.mp4``, ``.avi``, ``.mov``, ``.mkv``, ``.gif``
``.avi``, ``.mov``,
``.mkv``)
Images (``.jpg``,  any of these image types + ``.pdf``
``.jpeg``, ``.png``,
``.tiff``, ``.bmp``)
``.pdf``           ``.jpg``, ``.png``, ``.docx``, ``.txt``
``.docx``          ``.pdf``, ``.txt``
``.txt``           ``.pdf``, ``.docx``
=================  ================================================

.. note::

   If nothing specialized applies, a generic FFmpeg conversion path is used.

Troubleshooting & FAQs
----------------------

**“FFmpeg conversion failed.”**  
Install FFmpeg and ensure ``ffmpeg`` runs from a terminal, then retry.
**PDF → DOCX/TXT or TXT → PDF fails with a Pandoc error.**  
Install **Pandoc** and keep it on your ``PATH``.

**DOCX → PDF fails.**  
``docx2pdf`` requires Microsoft Word on Windows/macOS. If Word is not installed, open the
DOCX in Word and export to PDF manually.

**“CSV must include a 'file_name' column.”**  
Adjust your CSV header to include ``file_name``; use column pairs named
``<name>_in`` and ``<name>_out``. :contentReference[oaicite:49]{index=49} :contentReference[oaicite:50]{index=50}

**“Overlapping intruder intervals” or “Exit before enter.”**  
Edit your annotations so each intruder has a non-overlapping range with ``exit ≥ enter``. :contentReference[oaicite:51]{index=51}

**SLEAP won’t start.**  
The app tries ``SLEAP_LABEL`` → PATH → ``conda run -n sleap sleap-label``. Check that
SLEAP is installed, PATH is set, and Conda is available. :contentReference[oaicite:52]{index=52} :contentReference[oaicite:53]{index=53}

Appendix — command line entrypoint
----------------------------------

* Installed script: :code:`mouse-trap`
* Entrypoint: :code:`mouse_trap.__main__:main`
* Package name: :code:`mouse-trap` (requires Python ≥ 3.9) :contentReference[oaicite:54]{index=54} :contentReference[oaicite:55]{index=55}

Package modules
---------------

* :mod:`conversion` — conversion helpers and worker thread. :contentReference[oaicite:56]{index=56}
* :mod:`annotation` — interactive video annotation dialog. :contentReference[oaicite:57]{index=57}
* :mod:`sleap_cli` — SLEAP batch dialog, CLI spec, and runner. :contentReference[oaicite:58]{index=58}
* :mod:`gui` — main window and all GUI actions. :contentReference[oaicite:59]{index=59}
* :mod:`__main__` — application entry point. :contentReference[oaicite:60]{index=60}
* :mod:`__init__` — public exports. :contentReference[oaicite:61]{index=61}
