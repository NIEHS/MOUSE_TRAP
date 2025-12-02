"""Main window for converting files, clipping videos by annotations, and launching SLEAP tools."""

import os
from pathlib import Path

from PyQt6.QtCore import pyqtSlot, Qt, QProcess
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListView,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from .conversion import video_to_avi, ConversionThread
from .annotation import VideoAnnotationDialog
from .sleap_cli import SleapBatchDialog, SleapBatchThread
from typing import Dict, Tuple


class MainWindow(QMainWindow):
    """Desktop GUI for conversions, annotation-based clipping, and SLEAP helpers.

    The window provides three workflows:

    1) Convert videos, images, or documents with a progress bar and console.
    2) Clip videos by (enter, exit) frame annotations collected in a dialog.
    3) SLEAP: launch the labeler or run batch inference from a guided form.

    Attributes:
        input_file: The currently selected file when processing one item.
        input_files: List of files selected when running a batch.
        output_file: Destination path computed for the active item.
        output_folder: Optional override directory for outputs.
        current_extension: Lower-cased file extension of the active input.
        file_list: The queue of files to process.
        current_file_index: Index into ``file_list`` for batch processing.
        temp_avi_file: Temporary MJPEG AVI used for precise frame scrubbing.
        csv_annotations_mapping: Optional mapping loaded from CSV.
        OUTPUT_FORMATS: Map of input extension → list of allowed output extensions.

    """

    def __init__(self) -> None:
        """Build the UI and initialize state."""
        super().__init__()
        self.setWindowTitle("Multi-Format File Converter & Video Annotator")
        self.resize(900, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)

        banner_layout = QHBoxLayout()
        self.logo_label = QLabel()
        # Locate logo relative to this module (safe inside a package)
        logo_path = Path(__file__).parent / "media" / "nih_logo.png"
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            self.logo_label.setPixmap(
                pixmap.scaledToHeight(50, Qt.TransformationMode.SmoothTransformation)
            )
        banner_layout.addWidget(self.logo_label)
        banner_label = QLabel("Multi-Format File Converter & Video Annotator")
        banner_label.setStyleSheet("font-size: 24px; font-weight: bold; color: white;")
        banner_layout.addWidget(banner_label)
        banner_layout.addStretch()
        banner_widget = QWidget()
        banner_widget.setLayout(banner_layout)
        banner_widget.setStyleSheet("background-color: #205493;")
        main_layout.addWidget(banner_widget, 1)

        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)

        file_layout = QHBoxLayout()
        self.file_label = QLabel("No file selected")
        self.select_file_button = QPushButton("Select File")
        self.select_file_button.clicked.connect(self.select_file)
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(self.select_file_button)
        self.select_folder_button = QPushButton("Select Input Folder")
        self.select_folder_button.clicked.connect(self.select_folders_and_filter)
        self.recursive_checkbox = QCheckBox("Include subfolders")
        self.recursive_checkbox.setChecked(False)
        file_layout.addWidget(self.select_folder_button)
        file_layout.addWidget(self.recursive_checkbox)
        bottom_layout.addLayout(file_layout)

        options_group_layout = QVBoxLayout()
        options_layout = QHBoxLayout()
        self.multiple_files_checkbox = QCheckBox("Select Multiple Files")
        options_layout.addWidget(self.multiple_files_checkbox)
        self.output_folder_checkbox = QCheckBox("Select Output Folder")
        options_layout.addWidget(self.output_folder_checkbox)
        self.output_folder_button = QPushButton("Choose Folder")
        self.output_folder_button.setEnabled(False)
        self.output_folder_button.clicked.connect(self.select_output_folder)
        options_layout.addWidget(self.output_folder_button)
        options_layout.addStretch()
        options_group_layout.addLayout(options_layout)
        self.output_folder_checkbox.stateChanged.connect(
            self.toggle_output_folder_button
        )

        annotation_layout = QHBoxLayout()
        self.clip_checkbox = QCheckBox("Clip")
        annotation_layout.addWidget(self.clip_checkbox)
        self.select_annotation_file_button = QPushButton("Import CSV Annotations")
        self.select_annotation_file_button.clicked.connect(
            self.import_csv_annotations_multi
        )
        self.select_annotation_file_button.setSizePolicy(
            QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        )
        annotation_layout.addWidget(self.select_annotation_file_button)
        self.sleap_button = QPushButton("Launch SLEAP")
        self.sleap_button.clicked.connect(self.launch_sleap)
        self.sleap_button.setSizePolicy(
            QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        )
        annotation_layout.addWidget(self.sleap_button)
        self.sleap_batch_button = QPushButton("Run SLEAP Inference")
        self.sleap_batch_button.clicked.connect(self.start_sleap_batch)
        self.sleap_batch_button.setSizePolicy(
            QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        )
        annotation_layout.addWidget(self.sleap_batch_button)

        annotation_layout.addStretch()
        options_group_layout.addLayout(annotation_layout)

        output_layout = QHBoxLayout()
        self.output_label = QLabel("Output Format:")
        self.output_combo = QComboBox()
        self.output_combo.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        output_layout.addWidget(self.output_label)
        output_layout.addWidget(self.output_combo)
        output_layout.addStretch()
        options_group_layout.addLayout(output_layout)
        bottom_layout.addLayout(options_group_layout)

        self.convert_button = QPushButton("Convert")
        self.convert_button.clicked.connect(self.start_conversion)
        bottom_layout.addWidget(self.convert_button)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        bottom_layout.addWidget(self.progress_bar)
        self.console = QPlainTextEdit(self)
        self.console.setReadOnly(True)
        self.console.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        try:
            self.console.setFont(QFont("Consolas", 10))
        except Exception:
            pass
        bottom_layout.addWidget(self.console)
        bottom_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        bottom_container.setMaximumHeight(bottom_container.sizeHint().height())
        main_layout.addWidget(bottom_container, 0)

        self.input_file = None
        self.input_files = None
        self.output_file = None
        self.output_folder = None
        self.current_extension = None
        self.file_list = []
        self.current_file_index = 0
        self.annotation_file = None
        self.temp_avi_file = None
        self.csv_annotations_mapping = {}

        self.OUTPUT_FORMATS = {
            ".seq": [".mp4", ".avi"],
            ".avi": [".mp4", ".avi", ".mov", ".mkv", ".gif"],
            ".mov": [".mp4", ".avi", ".mov", ".mkv", ".gif"],
            ".mkv": [".mp4", ".avi", ".mov", ".mkv", ".gif"],
            ".mp4": [".mp4", ".avi", ".mov", ".mkv", ".gif"],
            ".jpg": [".jpg", ".png", ".tiff", ".bmp", ".pdf"],
            ".jpeg": [".jpg", ".png", ".tiff", ".bmp", ".pdf"],
            ".png": [".jpg", ".png", ".tiff", ".bmp", ".pdf"],
            ".tiff": [".jpg", ".png", ".tiff", ".bmp", ".pdf"],
            ".bmp": [".jpg", ".png", ".tiff", ".bmp", ".pdf"],
            ".pdf": [".jpg", ".png", ".docx", ".txt"],
            ".docx": [".pdf", ".txt"],
            ".txt": [".pdf", ".docx"],
        }
        self.setStyleSheet("QMainWindow { background-color: #FFFFFF; }")

    def _append_console(self, s: str) -> None:
        """Append a single line to the scrollback console.

        Gracefully no-ops if the widget is unavailable (e.g., during teardown).
        """
        try:
            if s:
                self.console.appendPlainText(s.rstrip("\n"))
        except Exception:
            pass

    def _append_process_output(self, proc: QProcess) -> None:
        """Stream the standard output of a running :class:`QProcess` into the console.

        Each line is appended as it becomes available.
        """
        try:
            data = proc.readAllStandardOutput().data().decode(errors="ignore")
            if data:
                for ln in data.splitlines():
                    self._append_console(ln)
        except Exception:
            pass

    def toggle_output_folder_button(self, state: int) -> None:
        """Enable/disable the output-folder picker and clear state when disabled.

        Args:
            state: The checked state from the Select Output Folder checkbox.

        """
        if state == Qt.CheckState.Checked.value:
            self.output_folder_button.setEnabled(True)
        else:
            self.output_folder_button.setEnabled(False)
            self.output_folder = None

    def select_output_folder(self) -> None:
        """Open a folder picker and save the chosen directory as the output target."""
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_folder = folder

    def select_file(self) -> None:
        """Pick one or many input files and refresh allowed output formats.

        Behavior depends on the Select Multiple Files checkbox. When multiple
        files are selected, the first file determines the output-format menu.
        """
        file_dialog = QFileDialog()
        if self.multiple_files_checkbox.isChecked():
            file_paths, _ = file_dialog.getOpenFileNames(
                self, "Select files to convert"
            )
            if file_paths:
                self.input_files = [Path(fp) for fp in file_paths]
                self.file_label.setText(f"{len(self.input_files)} files selected")
                self.input_file = self.input_files[0]
                self.current_extension = self.input_file.suffix.lower()
                self.update_output_options()
        else:
            file_path, _ = file_dialog.getOpenFileName(self, "Select a file to convert")
            if file_path:
                self.input_file = Path(file_path)
                self.file_label.setText(self.input_file.name)
                self.current_extension = self.input_file.suffix.lower()
                self.update_output_options()

    def select_folders_and_filter(self) -> None:
        """Queue files from one or more folders filtered by extension.

        The user selects folders, optionally includes subfolders, and provides an
        extension (e.g., ``.mp4``). Matching files are de-duplicated and queued.

        Notes:
            If no matches are found, a No Files message is shown.

        """
        dialog = QFileDialog(self, "Select Input Folders")
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
        for view in dialog.findChildren((QListView, QTreeView)):
            view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        if dialog.exec() != QFileDialog.DialogCode.Accepted:
            return
        folders = [Path(p) for p in dialog.selectedFiles() if p]
        if not folders:
            return
        file_type, ok = QInputDialog.getText(
            self, "File Type Filter", "Enter file extension (e.g., .seq or .avi):"
        )
        if not ok or not file_type:
            return
        ext = file_type.lower().strip()
        if ext and not ext.startswith("."):
            ext = "." + ext
        recursive = (
            hasattr(self, "recursive_checkbox") and self.recursive_checkbox.isChecked()
        )
        filtered_files = []
        for folder_path in folders:
            if not (folder_path.exists() and folder_path.is_dir()):
                continue
            if recursive:
                for f in folder_path.rglob("*"):
                    if f.is_file() and f.suffix.lower() == ext:
                        filtered_files.append(f)
            else:
                for f in folder_path.iterdir():
                    if f.is_file() and f.suffix.lower() == ext:
                        filtered_files.append(f)
        seen = set()
        filtered_files = [f for f in filtered_files if not (f in seen or seen.add(f))]
        if filtered_files:
            self.input_files = filtered_files
            self.file_label.setText(
                f"{len(filtered_files)} files from {len(folders)} folder(s) "
                f"selected with type {ext}" + (" (recursive)" if recursive else "")
            )
            self.input_file = filtered_files[0]
            self.current_extension = self.input_file.suffix.lower()
            self.update_output_options()
        else:
            QMessageBox.information(
                self,
                "No Files",
                f"No files with extension {ext} found in the selected folder(s)"
                + (" (recursive)." if recursive else "."),
            )

    def update_output_options(self) -> None:
        """Populate the Output Format combo for the active input extension.

        If the extension is unknown, defaults to ``.mp4``.
        """
        self.output_combo.clear()
        if self.current_extension in self.OUTPUT_FORMATS:
            self.output_combo.addItems(self.OUTPUT_FORMATS[self.current_extension])
        else:
            self.output_combo.addItem(".mp4")

    def import_csv_annotations_multi(self) -> None:
        """Load (per-file) intruder intervals from a CSV into memory.

        The CSV must include a ``file_name`` column and any number of ``<name>_in``
        / ``<name>_out`` pairs. Errors are reported via message boxes, and the
        in-memory mapping is updated on success.
        """
        fileName, _ = QFileDialog.getOpenFileName(
            self, "Import CSV Annotations for Multiple Files", "", "CSV Files (*.csv)"
        )
        if not fileName:
            return
        mapping = {}
        import csv

        try:
            with open(fileName, newline="", encoding="utf-8-sig") as csvfile:
                reader = csv.DictReader(csvfile)
                headers = reader.fieldnames
                if headers is None or "file_name" not in [h.strip() for h in headers]:
                    QMessageBox.critical(
                        self,
                        "CSV Error",
                        f"CSV must include a 'file_name' column. Found headers: {headers}",
                    )
                    return
                for row in reader:
                    fname = row.get("file_name", "").strip()
                    if not fname:
                        continue
                    annotations = {}
                    for key, value in row.items():
                        key_clean = key.strip()
                        if key_clean == "file_name":
                            continue
                        if value.strip() == "":
                            continue
                        if key_clean.endswith("_in"):
                            intruder = key_clean[:-3]
                            if intruder not in annotations:
                                annotations[intruder] = {}
                            annotations[intruder]["enter"] = int(value)
                        elif key_clean.endswith("_out"):
                            intruder = key_clean[:-4]
                            if intruder not in annotations:
                                annotations[intruder] = {}
                            annotations[intruder]["exit"] = int(value)
                    mapping[fname] = annotations
        except Exception as e:
            QMessageBox.critical(self, "CSV Error", f"Error reading CSV: {str(e)}")
            return
        self.csv_annotations_mapping = mapping
        QMessageBox.information(
            self, "CSV Imported", "CSV annotations mapping imported successfully."
        )

    def start_conversion(self) -> None:
        """Kick off processing for the current selection.

        Prompts whether to confirm each file in multi-file mode, then seeds
        :attr:`file_list` and calls :meth:`process_next_file`.
        """
        reply = QMessageBox.question(
            self,
            "Prompt Setting",
            "Do you want to be prompted on every file?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        self.prompt_on_each_file = reply == QMessageBox.StandardButton.Yes
        if self.multiple_files_checkbox.isChecked() and self.input_files:
            self.file_list = self.input_files
            self.current_file_index = 0
            self.process_next_file()
        elif self.input_file:
            self.file_list = [self.input_file]
            self.current_file_index = 0
            self.process_next_file()
        else:
            QMessageBox.warning(self, "Warning", "No input file selected.")
            return

    def process_next_file(self) -> None:
        """Process the next file in the queue.

        Handles per-file prompts, resolves output paths, runs either the
        clip workflow (with temporary AVI and annotation dialog) or the
        standard conversion workflow via :class:`ConversionThread`. Advances
        the queue and updates progress UI accordingly.
        """
        if self.current_file_index < len(self.file_list):
            self.input_file = self.file_list[self.current_file_index]
            self.current_extension = self.input_file.suffix.lower()
            if self.prompt_on_each_file and len(self.file_list) > 1:
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Process File?")
                msg_box.setText(f"Do you want to process {self.input_file.name}?")
                msg_box.addButton("Yes", QMessageBox.ButtonRole.YesRole)
                no_button = msg_box.addButton("No", QMessageBox.ButtonRole.NoRole)
                exit_button = msg_box.addButton(
                    "Exit", QMessageBox.ButtonRole.RejectRole
                )

                msg_box.exec()
                clicked = msg_box.clickedButton()

                if clicked == no_button:
                    self.current_file_index += 1
                    self.progress_bar.setValue(0)
                    self.process_next_file()
                    return
                elif clicked == exit_button:
                    QMessageBox.information(
                        self,
                        "Conversion Cancelled",
                        "Conversion process cancelled by user.",
                    )
                    self.convert_button.setEnabled(True)
                    self.select_file_button.setEnabled(True)
                    return

            output_ext = self.output_combo.currentText()
            if self.output_folder and self.output_folder_checkbox.isChecked():
                self.output_file = Path(self.output_folder) / (
                    self.input_file.stem + output_ext
                )
            else:
                self.output_file = self.input_file.with_suffix(output_ext)

            if self.clip_checkbox.isChecked():
                if self.current_extension not in [".seq", ".mp4", ".avi"]:
                    QMessageBox.critical(
                        self,
                        "Error",
                        "Clipped output is only supported for .seq, .mp4, or .avi input in this example.",
                    )
                    self.convert_button.setEnabled(True)
                    self.select_file_button.setEnabled(True)
                    return
                if output_ext == ".gif":
                    QMessageBox.critical(
                        self, "Error", "GIF output is not supported for clipping."
                    )
                    self.convert_button.setEnabled(True)
                    self.select_file_button.setEnabled(True)
                    return
                if self.current_extension in [".seq", ".mp4"]:
                    self.temp_avi_file = self.input_file.parent / (
                        self.input_file.stem + "_temp.avi"
                    )
                    success, message = video_to_avi(self.input_file, self.temp_avi_file)
                    if not success:
                        QMessageBox.critical(self, "Error", message)
                        self.convert_button.setEnabled(True)
                        self.select_file_button.setEnabled(True)
                        return
                elif self.current_extension == ".avi":
                    self.temp_avi_file = self.input_file

                annot_dialog = VideoAnnotationDialog(self.temp_avi_file)
                key = self.input_file.stem
                if self.csv_annotations_mapping and key in self.csv_annotations_mapping:
                    annot_dialog.annotations.update(self.csv_annotations_mapping[key])
                if annot_dialog.exec() == QDialog.DialogCode.Accepted:
                    annotations = annot_dialog.annotations
                    success, message = self.clip_by_annotations(
                        annotations, self.temp_avi_file
                    )
                    if success:
                        QMessageBox.information(self, "Success", message)
                    else:
                        QMessageBox.critical(self, "Error", message)
                else:
                    QMessageBox.warning(self, "Annotation", "Annotation cancelled.")

                try:
                    if (
                        self.current_extension in [".seq", ".mp4"]
                        and self.temp_avi_file.exists()
                    ):
                        os.remove(self.temp_avi_file)
                except Exception:
                    pass

                self.current_file_index += 1
                self.progress_bar.setValue(0)
                self.process_next_file()
                return

            conversion_type = self.determine_conversion_type(
                self.current_extension, output_ext
            )
            self.thread = ConversionThread(
                input_file=self.input_file,
                output_file=self.output_file,
                conversion_type=conversion_type,
            )
            self.thread.progress_signal.connect(self.update_progress)
            self.thread.finished_signal.connect(self.on_conversion_finished)
            self.convert_button.setEnabled(False)
            self.select_file_button.setEnabled(False)
            self.thread.start()
        else:
            QMessageBox.information(self, "Success", "All conversions completed.")
            self.convert_button.setEnabled(True)
            self.select_file_button.setEnabled(True)

    def determine_conversion_type(self, input_ext: str, output_ext: str) -> str:
        """Return the conversion key for a given input/output pair.

        Args:
            input_ext: Lower-cased input extension (e.g., ``.mp4``).
            output_ext: Selected output extension (e.g., ``.avi``).

        Returns:
            A conversion key such as ``"video_to_video"``.

        """
        if input_ext == ".seq" and output_ext == ".mp4":
            return "seq_to_mp4"
        elif input_ext == ".seq" and output_ext == ".avi":
            return "seq_to_avi"
        elif input_ext == ".mp4" and output_ext == ".avi":
            return "video_to_avi"
        video_exts = [".mp4", ".avi", ".mov", ".mkv", ".gif"]
        if input_ext in video_exts and output_ext in video_exts:
            return "video_to_video"
        image_exts = [".jpg", ".jpeg", ".png", ".tiff", ".bmp"]
        if input_ext in image_exts and output_ext in image_exts:
            return "image_to_image"
        if input_ext in image_exts and output_ext == ".pdf":
            return "image_to_pdf"
        if input_ext == ".pdf" and output_ext in image_exts:
            return "pdf_to_image"
        if input_ext == ".pdf" and output_ext == ".docx":
            return "pdf_to_docx"
        if input_ext == ".pdf" and output_ext == ".txt":
            return "pdf_to_txt"
        if input_ext == ".docx" and output_ext == ".pdf":
            return "docx_to_pdf"
        if input_ext == ".docx" and output_ext == ".txt":
            return "docx_to_txt"
        if input_ext == ".txt" and output_ext == ".pdf":
            return "txt_to_pdf"
        if input_ext == ".txt" and output_ext == ".docx":
            return "txt_to_docx"
        return "generic_conversion"

    @pyqtSlot(int)
    def update_progress(self, value: int) -> None:
        """Update the progress bar to ``value`` percent."""
        self.progress_bar.setValue(value)

    @pyqtSlot(bool, str)
    def on_conversion_finished(self, success: bool, message: str) -> None:
        """Handle completion of a conversion.

        On failure, shows a modal error and re-enables controls. On success,
        advances the queue by calling :meth:`process_next_file`.
        """
        if not success:
            QMessageBox.critical(self, "Error", message)
            self.convert_button.setEnabled(True)
            self.select_file_button.setEnabled(True)
            return
        self.current_file_index += 1
        self.progress_bar.setValue(0)
        self.process_next_file()

    def clip_by_annotations(
        self, annotations: Dict[str, Dict[str, int]], video_path: Path
    ) -> Tuple[bool, str]:
        """Write one output clip per intruder interval.

        Validates intervals (both enter/exit set, exit ≥ enter, no overlaps), opens
        the source video, and writes a clip per intruder using a format-specific codec.

        Args:
            annotations: Mapping of intruder name → ``{"enter": int, "exit": int}``.
            video_path: Path to the frame-accurate source (the temp AVI or original AVI).

        Returns:
            Tuple[bool, str]: ``(success, message)`` summarizing the result.

        """
        intervals = []
        for intruder, data in annotations.items():
            if "enter" not in data or "exit" not in data:
                return False, f"Incomplete annotation for intruder '{intruder}'."
            enter_frame = data["enter"]
            exit_frame = data["exit"]
            if exit_frame < enter_frame:
                return (
                    False,
                    f"Exit frame occurs before enter frame for intruder '{intruder}'.",
                )
            intervals.append((enter_frame, exit_frame, intruder))

        intervals.sort(key=lambda x: x[0])
        for i in range(len(intervals) - 1):
            if intervals[i + 1][0] <= intervals[i][1]:
                return False, (
                    "Overlapping intruder intervals found between "
                    f"'{intervals[i][2]}' and '{intervals[i + 1][2]}'."
                )

        import cv2

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return False, f"Could not open {video_path} for clipping."
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 25
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        ext = self.output_file.suffix.lower()
        codec_map = {".mp4": "mp4v", ".avi": "MJPG", ".mov": "mp4v", ".mkv": "mp4v"}
        codec_str = codec_map.get(ext, "mp4v")
        fourcc = cv2.VideoWriter_fourcc(*codec_str)
        for enter_frame, exit_frame, intruder in intervals:
            output_name = (
                f"{self.output_file.stem}_{intruder}intruder{self.output_file.suffix}"
            )
            if self.output_folder and self.output_folder_checkbox.isChecked():
                out_path = Path(self.output_folder) / output_name
            else:
                out_path = self.output_file.parent / output_name
            out_writer = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height))
            cap.set(cv2.CAP_PROP_POS_FRAMES, enter_frame - 1)
            while True:
                current_idx = cap.get(cv2.CAP_PROP_POS_FRAMES)
                if current_idx >= exit_frame:
                    break
                ret, frame = cap.read()
                if not ret:
                    break
                out_writer.write(frame)
            out_writer.release()
        cap.release()
        return True, f"Successfully clipped intruders for file {self.input_file.name}."

    def launch_sleap(self) -> None:
        """Launch *SLEAP Label* and stream its console output.

        Resolution order is:

        1) ``SLEAP_LABEL`` environment variable.
        2) ``sleap-label`` on ``PATH``.
        3) ``conda run -n sleap sleap-label`` using a discovered conda executable.

        Shows a message if startup fails.
        """
        try:
            proc = QProcess(self)
            proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            proc.readyReadStandardOutput.connect(
                lambda: self._append_process_output(proc)
            )

            def _finished(exitCode, _status):
                self._append_console(f"SLEAP exited with code {exitCode}")
                self.sleap_button.setEnabled(True)

            proc.finished.connect(_finished)

            def _err(_):
                self._append_console("Failed to start SLEAP process.")
                self.sleap_button.setEnabled(True)

            proc.errorOccurred.connect(_err)

            sleap_label = os.environ.get("SLEAP_LABEL", "")
            if sleap_label and os.path.exists(sleap_label):
                program = sleap_label
                args = []
            else:
                from shutil import which

                found = which("sleap-label")
                if found:
                    program = found
                    args = []
                else:
                    from .sleap_cli import _resolve_conda_executable

                    conda_executable = _resolve_conda_executable()
                    if os.name == "nt":
                        conda_cmd = (
                            f'"{conda_executable}"'
                            if " " in conda_executable
                            else conda_executable
                        )
                        program = "cmd.exe"
                        args = [
                            "/d",
                            "/c",
                            conda_cmd,
                            "run",
                            "--no-capture-output",
                            "-n",
                            "sleap",
                            "sleap-label",
                        ]
                    else:
                        program = conda_executable
                        args = [
                            "run",
                            "--no-capture-output",
                            "-n",
                            "sleap",
                            "sleap-label",
                        ]

            self._append_console(f"Launching: {program} {' '.join(args)}")
            self.sleap_button.setEnabled(False)
            proc.setProgram(program)
            proc.setArguments(args)
            proc.start()

            if not proc.waitForStarted(5000):
                QMessageBox.critical(
                    self,
                    "Error",
                    "Failed to start SLEAP. Check your conda env and PATH.",
                )
                self.sleap_button.setEnabled(True)
                return

            self.sleap_process = proc

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error launching SLEAP: {str(e)}")
            self.sleap_button.setEnabled(True)

    def start_sleap_batch(self) -> None:
        """Collect parameters and run sleap-nn track jobs in a worker thread.

        Opens :class:`SleapBatchDialog`, then constructs :class:`SleapBatchThread`,
        wires up progress and line streaming, and starts the thread.
        """
        dlg = SleapBatchDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        params = dlg.values()
        self.sleapThread = SleapBatchThread(params, self)
        self.sleapThread.progress.connect(self._on_sleap_progress)
        self.sleapThread.line.connect(self._on_sleap_line)
        self.sleapThread.done.connect(self._on_sleap_done)
        try:
            self.progress_bar.setValue(0)
        except Exception:
            pass
        self.sleap_batch_button.setEnabled(False)
        self.sleapThread.start()

    def _on_sleap_progress(self, percent: int, name: str) -> None:
        """Update the progress bar during batch inference."""
        try:
            self.progress_bar.setValue(percent)
        except Exception:
            pass

    def _on_sleap_line(self, text: str) -> None:
        """Append one line of output from the SLEAP CLI to the console."""
        self._append_console(text)

    def _on_sleap_done(self) -> None:
        """Re-enable the Run SLEAP Inference button and notify the user."""
        self.sleap_batch_button.setEnabled(True)
        QMessageBox.information(self, "SLEAP", "Batch inference finished.")
