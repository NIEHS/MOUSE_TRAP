"""
Neurobehavioral Circuits Group Multi-Format File Converter (Full Code)
----------------------------------------------------------------------
This single-file PyQt6 application contains code for converting various
file types (videos, images, PDFs, DOCX, TXT, etc.), including .seq -> .mp4
(via OpenCV) and a fallback "generic_conversion" using ffmpeg if needed.
It also now supports clipping .seq files using an annotation file.
"""

import sys
import os
import subprocess
from pathlib import Path

# -------------------------------------------
# PyQt6 imports
# -------------------------------------------
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QLabel, QVBoxLayout,
    QHBoxLayout, QComboBox, QFileDialog, QProgressBar, QMessageBox,
    QSizePolicy, QCheckBox
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot

# -------------------------------------------
# OpenCV for .seq -> .mp4 (if your .seq is compatible)
# -------------------------------------------
import cv2

# -------------------------------------------
# Pillow for Image conversions
# -------------------------------------------
from PIL import Image

# -------------------------------------------
# pdf2image for PDF -> Image
# -------------------------------------------
from pdf2image import convert_from_path

# -------------------------------------------
# pypandoc for PDF <-> DOCX/TXT, TXT <-> PDF/DOCX
# -------------------------------------------
import pypandoc

# -------------------------------------------
# docx2pdf for DOCX -> PDF
# -------------------------------------------
from docx2pdf import convert as docx2pdf_convert


###############################################################################
# Conversion Thread
###############################################################################
class ConversionThread(QThread):
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)  # (success_flag, message)

    def __init__(self, input_file, output_file, conversion_type, parent=None):
        super().__init__(parent)
        self.input_file = Path(input_file)
        self.output_file = Path(output_file)
        self.conversion_type = conversion_type

    def run(self):
        """
        Perform the conversion based on the determined conversion_type.
        """
        try:
            success, msg = False, "Unknown conversion"
            if self.conversion_type == 'seq_to_mp4':
                success, msg = self.seq_to_mp4()
            elif self.conversion_type == 'video_to_video':
                success, msg = self.ffmpeg_video_convert()
            elif self.conversion_type == 'image_to_image':
                success, msg = self.image_to_image()
            elif self.conversion_type == 'image_to_pdf':
                success, msg = self.image_to_pdf()
            elif self.conversion_type == 'pdf_to_image':
                success, msg = self.pdf_to_image()
            elif self.conversion_type == 'pdf_to_docx':
                success, msg = self.pdf_to_docx()
            elif self.conversion_type == 'pdf_to_txt':
                success, msg = self.pdf_to_txt()
            elif self.conversion_type == 'docx_to_pdf':
                success, msg = self.docx_to_pdf()
            elif self.conversion_type == 'docx_to_txt':
                success, msg = self.docx_to_txt()
            elif self.conversion_type == 'txt_to_pdf':
                success, msg = self.txt_to_pdf()
            elif self.conversion_type == 'txt_to_docx':
                success, msg = self.txt_to_docx()
            else:
                # Fallback to ffmpeg-based approach
                success, msg = self.generic_conversion()

            self.finished_signal.emit(success, msg)

        except Exception as e:
            self.finished_signal.emit(False, str(e))

    # -------------------------------------------------------------------------
    # 1) .seq -> .mp4 (OpenCV-based approach)
    # -------------------------------------------------------------------------
    def seq_to_mp4(self):
        """
        Convert .seq to .mp4 using OpenCV.
        This assumes your .seq file is readable by cv2.VideoCapture.
        """
        cap = cv2.VideoCapture(str(self.input_file))
        if not cap.isOpened():
            return False, f"Could not open {self.input_file} as .seq."

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            # fallback if FPS is not set
            fps = 30
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(self.output_file), fourcc, fps, (width, height))

        frame_count = 0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            out.write(frame)
            frame_count += 1

            # Update progress
            if total_frames > 0:
                progress_percent = int((frame_count / total_frames) * 100)
                self.progress_signal.emit(progress_percent)

        cap.release()
        out.release()
        return True, f"Converted .seq to .mp4: {self.output_file}"

    # -------------------------------------------------------------------------
    # 2) Video -> Video (via ffmpeg)
    # -------------------------------------------------------------------------
    def ffmpeg_video_convert(self):
        """
        Convert from one video format to another using ffmpeg.
        """
        cmd = [
            'ffmpeg',
            '-i', str(self.input_file),
            '-y',  # overwrite
            str(self.output_file)
        ]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, stderr = process.communicate()
        if process.returncode != 0:
            return False, f"FFmpeg error: {stderr.decode('utf-8')}"
        return True, f"Video conversion to {self.output_file} completed."

    # -------------------------------------------------------------------------
    # 3) Image -> Image (via Pillow)
    # -------------------------------------------------------------------------
    def image_to_image(self):
        """
        Convert between image formats (JPEG, PNG, BMP, TIFF, etc.) using Pillow.
        """
        try:
            img = Image.open(self.input_file)
            if img.mode in ["RGBA", "P"]:
                img = img.convert("RGB")
            img.save(self.output_file)
            return True, f"Image conversion to {self.output_file} completed."
        except Exception as e:
            return False, f"Image conversion failed: {str(e)}"

    # -------------------------------------------------------------------------
    # 4) Image -> PDF (via Pillow)
    # -------------------------------------------------------------------------
    def image_to_pdf(self):
        """
        Convert a single image to a single-page PDF using Pillow.
        """
        try:
            img = Image.open(self.input_file)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(self.output_file, "PDF")
            return True, f"Image -> PDF conversion to {self.output_file} completed."
        except Exception as e:
            return False, f"Image->PDF conversion failed: {str(e)}"

    # -------------------------------------------------------------------------
    # 5) PDF -> Image (via pdf2image)
    # -------------------------------------------------------------------------
    def pdf_to_image(self):
        """
        Convert each page of a PDF to an image using pdf2image + poppler.
        Multiple images will be saved as <output_stem>_page{i}.<ext>.
        """
        try:
            base_name = self.output_file.stem
            out_dir = self.output_file.parent
            out_ext = self.output_file.suffix

            images = convert_from_path(str(self.input_file))
            if not images:
                return False, f"No images extracted from {self.input_file}."

            for i, page_image in enumerate(images):
                out_file = out_dir / f"{base_name}_page{i}{out_ext}"
                if page_image.mode in ("RGBA", "P"):
                    page_image = page_image.convert("RGB")
                page_image.save(out_file)
            return True, f"PDF -> Image(s) in {out_dir} completed."
        except Exception as e:
            return False, f"PDF->Image conversion failed: {str(e)}"

    # -------------------------------------------------------------------------
    # 6) PDF -> DOCX (via pypandoc)
    # -------------------------------------------------------------------------
    def pdf_to_docx(self):
        """
        Convert PDF to DOCX using pypandoc (requires pandoc).
        """
        try:
            output = pypandoc.convert_file(str(self.input_file), 'docx', outputfile=str(self.output_file))
            if output:
                return False, f"pypandoc error: {output}"
            return True, f"PDF->DOCX conversion to {self.output_file} completed."
        except Exception as e:
            return False, f"PDF->DOCX failed: {str(e)}"

    # -------------------------------------------------------------------------
    # 7) PDF -> TXT (via pypandoc)
    # -------------------------------------------------------------------------
    def pdf_to_txt(self):
        """
        Convert PDF to plain text using pypandoc.
        """
        try:
            output = pypandoc.convert_file(str(self.input_file), 'plain', outputfile=str(self.output_file))
            if output:
                return False, f"pypandoc error: {output}"
            return True, f"PDF->TXT conversion to {self.output_file} completed."
        except Exception as e:
            return False, f"PDF->TXT failed: {str(e)}"

    # -------------------------------------------------------------------------
    # 8) DOCX -> PDF (via docx2pdf)
    # -------------------------------------------------------------------------
    def docx_to_pdf(self):
        """
        Convert DOCX -> PDF using docx2pdf.
        """
        try:
            docx2pdf_convert(str(self.input_file), str(self.output_file))
            return True, f"DOCX->PDF conversion to {self.output_file} completed."
        except Exception as e:
            return False, f"DOCX->PDF failed: {str(e)}"

    # -------------------------------------------------------------------------
    # 9) DOCX -> TXT (via pypandoc)
    # -------------------------------------------------------------------------
    def docx_to_txt(self):
        """
        Convert DOCX to plain text via pypandoc.
        """
        try:
            output = pypandoc.convert_file(str(self.input_file), 'plain', outputfile=str(self.output_file))
            if output:
                return False, f"pypandoc error: {output}"
            return True, f"DOCX->TXT conversion to {self.output_file} completed."
        except Exception as e:
            return False, f"DOCX->TXT failed: {str(e)}"

    # -------------------------------------------------------------------------
    # 10) TXT -> PDF (via pypandoc)
    # -------------------------------------------------------------------------
    def txt_to_pdf(self):
        """
        Convert a text file into PDF via pypandoc.
        """
        try:
            output = pypandoc.convert_file(str(self.input_file), 'pdf', outputfile=str(self.output_file))
            if output:
                return False, f"pypandoc error: {output}"
            return True, f"TXT->PDF conversion to {self.output_file} completed."
        except Exception as e:
            return False, f"TXT->PDF failed: {str(e)}"

    # -------------------------------------------------------------------------
    # 11) TXT -> DOCX (via pypandoc)
    # -------------------------------------------------------------------------
    def txt_to_docx(self):
        """
        Convert a text file to DOCX via pypandoc.
        """
        try:
            output = pypandoc.convert_file(str(self.input_file), 'docx', outputfile=str(self.output_file))
            if output:
                return False, f"pypandoc error: {output}"
            return True, f"TXT->DOCX conversion to {self.output_file} completed."
        except Exception as e:
            return False, f"TXT->DOCX failed: {str(e)}"

    # -------------------------------------------------------------------------
    # Fallback: Generic Conversion (via ffmpeg)
    # -------------------------------------------------------------------------
    def generic_conversion(self):
        """
        Fallback to ffmpeg-based approach for any other combination.
        """
        cmd = [
            'ffmpeg',
            '-i', str(self.input_file),
            '-y',
            str(self.output_file)
        ]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, stderr = process.communicate()
        if process.returncode != 0:
            return False, f"FFmpeg error: {stderr.decode('utf-8')}"
        return True, f"Generic conversion to {self.output_file} completed."


###############################################################################
# MainWindow (PyQt6 GUI)
###############################################################################
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Neurobehavioral Circuits Group Multi-Format File Converter")
        self.resize(900, 600)

        # Create the central widget and main layout.
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)  # Preserve horizontal margins

        # ------------------------------
        # Create the blue banner widget.
        # ------------------------------
        banner_layout = QHBoxLayout()
        self.logo_label = QLabel()
        logo_path = os.path.join('media', 'nih_logo.png')
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            self.logo_label.setPixmap(pixmap.scaledToHeight(50, Qt.TransformationMode.SmoothTransformation))
        banner_layout.addWidget(self.logo_label)

        banner_label = QLabel("Neurobehavioral Circuits Group Multi-Format File Converter")
        banner_label.setStyleSheet("font-size: 24px; font-weight: bold; color: white;")
        banner_layout.addWidget(banner_label)
        banner_layout.addStretch()

        banner_widget = QWidget()
        banner_widget.setLayout(banner_layout)
        banner_widget.setStyleSheet("background-color: #205493;")

        # ------------------------------
        # Create a container for the bottom (fixed) part.
        # ------------------------------
        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)

        # File selection layout.
        file_layout = QHBoxLayout()
        self.file_label = QLabel("No file selected")
        self.select_file_button = QPushButton("Select File")
        self.select_file_button.clicked.connect(self.select_file)
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(self.select_file_button)
        bottom_layout.addLayout(file_layout)

        # Options group layout.
        options_group_layout = QVBoxLayout()

        # Row 1: Additional Options: Multiple Files and Output Folder.
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
        self.output_folder_checkbox.stateChanged.connect(self.toggle_output_folder_button)

        # Row 2: Clipping Options.
        annotation_layout = QHBoxLayout()
        self.clip_checkbox = QCheckBox("Clip using annotation file")
        self.clip_checkbox.stateChanged.connect(self.on_clip_checkbox_changed)
        annotation_layout.addWidget(self.clip_checkbox)
        
        self.select_annotation_file_button = QPushButton("Select Annotation File")
        self.select_annotation_file_button.setEnabled(False)
        self.select_annotation_file_button.clicked.connect(self.select_annotation_file)
        self.select_annotation_file_button.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed))
        annotation_layout.addWidget(self.select_annotation_file_button)
        
        self.annotation_file_label = QLabel("No annotation file selected")
        annotation_layout.addWidget(self.annotation_file_label)
        annotation_layout.addStretch()
        options_group_layout.addLayout(annotation_layout)

        # Row 3: Output Format.
        output_layout = QHBoxLayout()
        self.output_label = QLabel("Output Format:")
        self.output_combo = QComboBox()
        self.output_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        output_layout.addWidget(self.output_label)
        output_layout.addWidget(self.output_combo)
        output_layout.addStretch()
        options_group_layout.addLayout(output_layout)

        bottom_layout.addLayout(options_group_layout)

        # Convert Button + Progress Bar.
        self.convert_button = QPushButton("Convert")
        self.convert_button.clicked.connect(self.start_conversion)
        bottom_layout.addWidget(self.convert_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        bottom_layout.addWidget(self.progress_bar)

        # Fix the bottom container height so it does not expand.
        bottom_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        bottom_container.setMaximumHeight(bottom_container.sizeHint().height())

        # ------------------------------
        # Add the banner and bottom container to the main layout.
        # ------------------------------
        main_layout.addWidget(banner_widget, 1)    # Banner takes extra vertical space.
        main_layout.addWidget(bottom_container, 0)   # Bottom remains fixed.

        # ----------------------------------------------------------------------
        # Internal State
        # ----------------------------------------------------------------------
        self.input_file = None
        self.input_files = None  # For multiple file selection
        self.output_file = None
        self.output_folder = None
        self.current_extension = None
        self.file_list = []
        self.current_file_index = 0

        # For clipping
        self.annotation_file = None

        # Extension -> possible outputs
        self.OUTPUT_FORMATS = {
            ".seq":  [".mp4"],
            ".avi":  [".mp4", ".avi", ".mov", ".mkv", ".gif"],
            ".mov":  [".mp4", ".avi", ".mov", ".mkv", ".gif"],
            ".mkv":  [".mp4", ".avi", ".mov", ".mkv", ".gif"],
            ".mp4":  [".mp4", ".avi", ".mov", ".mkv", ".gif"],
            ".jpg":  [".jpg", ".png", ".tiff", ".bmp", ".pdf"],
            ".jpeg": [".jpg", ".png", ".tiff", ".bmp", ".pdf"],
            ".png":  [".jpg", ".png", ".tiff", ".bmp", ".pdf"],
            ".tiff": [".jpg", ".png", ".tiff", ".bmp", ".pdf"],
            ".bmp":  [".jpg", ".png", ".tiff", ".bmp", ".pdf"],
            ".pdf":  [".jpg", ".png", ".docx", ".txt"],
            ".docx": [".pdf", ".txt"],
            ".txt":  [".pdf", ".docx"]
        }

        # Set a simple default style for the main window
        self.setStyleSheet("QMainWindow { background-color: #FFFFFF; }")

    # --------------------------------------------------------------------------
    # Folder selection toggle
    # --------------------------------------------------------------------------
    def toggle_output_folder_button(self, state):
        if state == Qt.CheckState.Checked.value:
            self.output_folder_button.setEnabled(True)
        else:
            self.output_folder_button.setEnabled(False)
            self.output_folder = None

    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_folder = folder

    # --------------------------------------------------------------------------
    # File selection
    # --------------------------------------------------------------------------
    def select_file(self):
        file_dialog = QFileDialog()
        if self.multiple_files_checkbox.isChecked():
            file_paths, _ = file_dialog.getOpenFileNames(self, "Select files to convert")
            if file_paths:
                self.input_files = [Path(fp) for fp in file_paths]
                self.file_label.setText(f"{len(self.input_files)} files selected")
                # Use the first file's extension for output options
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

    def update_output_options(self):
        """Update the output combo based on selected input file extension."""
        self.output_combo.clear()
        if self.current_extension in self.OUTPUT_FORMATS:
            self.output_combo.addItems(self.OUTPUT_FORMATS[self.current_extension])
        else:
            self.output_combo.addItem(".mp4")

    # --------------------------------------------------------------------------
    # Clipping checkbox and annotation file selection methods
    # --------------------------------------------------------------------------
    def on_clip_checkbox_changed(self, state):
        if state == Qt.CheckState.Checked.value:
            self.select_annotation_file_button.setEnabled(True)
        else:
            self.select_annotation_file_button.setEnabled(False)
            self.annotation_file = None
            self.annotation_file_label.setText("No annotation file selected")

    def select_annotation_file(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "Select Annotation File", filter="Text Files (*.txt)")
        if file_path:
            self.annotation_file = Path(file_path)
            self.annotation_file_label.setText(self.annotation_file.name)

    # --------------------------------------------------------------------------
    # Start conversion: process file list (and handle clipping if checked)
    # --------------------------------------------------------------------------
    def start_conversion(self):
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

    def process_next_file(self):
        if self.current_file_index < len(self.file_list):
            self.input_file = self.file_list[self.current_file_index]
            self.current_extension = self.input_file.suffix.lower()
            output_ext = self.output_combo.currentText()
            if self.output_folder and self.output_folder_checkbox.isChecked():
                self.output_file = Path(self.output_folder) / (self.input_file.stem + output_ext)
            else:
                self.output_file = self.input_file.with_suffix(output_ext)

            # If clipping is enabled, use the clipping branch
            if self.clip_checkbox.isChecked():
                if not self.annotation_file:
                    QMessageBox.warning(self, "Warning", "No annotation file selected.")
                    self.convert_button.setEnabled(True)
                    self.select_file_button.setEnabled(True)
                    return
                if self.current_extension != ".seq" or output_ext != ".mp4":
                    QMessageBox.critical(
                        self,
                        "Error",
                        "Clipped output is only supported for .seq -> .mp4 in this example."
                    )
                    self.convert_button.setEnabled(True)
                    self.select_file_button.setEnabled(True)
                    return
                # Perform clipping conversion (synchronously)
                success, message = self.clip_by_annotation()
                if success:
                    QMessageBox.information(self, "Success", message)
                else:
                    QMessageBox.critical(self, "Error", message)
                self.current_file_index += 1
                self.progress_bar.setValue(0)
                self.process_next_file()
                return

            # Otherwise, perform normal conversion via ConversionThread
            conversion_type = self.determine_conversion_type(self.current_extension, output_ext)
            self.thread = ConversionThread(
                input_file=self.input_file,
                output_file=self.output_file,
                conversion_type=conversion_type
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

    def determine_conversion_type(self, input_ext, output_ext):
        """
        Decide which conversion method to invoke based on input/output extension.
        """
        if input_ext == ".seq" and output_ext == ".mp4":
            return "seq_to_mp4"
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
    def update_progress(self, value):
        self.progress_bar.setValue(value)

    @pyqtSlot(bool, str)
    def on_conversion_finished(self, success, message):
        if not success:
            QMessageBox.critical(self, "Error", message)
            self.convert_button.setEnabled(True)
            self.select_file_button.setEnabled(True)
            return
        self.current_file_index += 1
        self.progress_bar.setValue(0)
        self.process_next_file()

    # --------------------------------------------------------------------------
    # Clipping conversion method: uses annotation file to clip .seq -> .mp4
    # --------------------------------------------------------------------------
    def clip_by_annotation(self):
        """
        Parse the annotation file for lines like:
            start_frame end_frame behavior_type
        (only considering *_enters and *_exit[s]) and then create a separate .mp4
        clip for each intruder. The output files are named as:
            <baseOutputName>_<intruderName>_1.mp4
        """
        intruders = {}  # { intruder_name: {'enters': (s,e), 'exit': (s,e)} }
        try:
            with open(self.annotation_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split()
                    if len(parts) != 3:
                        continue
                    start_str, end_str, behavior = parts
                    if not (behavior.endswith("_enters") or behavior.endswith("_exit") or behavior.endswith("_exits")):
                        continue
                    try:
                        start_frame = int(start_str)
                        end_frame = int(end_str)
                    except ValueError:
                        continue

                    if behavior.endswith("_enters"):
                        intruder_name = behavior[:-7]
                        if intruder_name not in intruders:
                            intruders[intruder_name] = {'enters': None, 'exit': None}
                        if intruders[intruder_name]['enters'] is not None:
                            return False, f"Multiple enters found for intruder '{intruder_name}'."
                        intruders[intruder_name]['enters'] = (start_frame, end_frame)
                    elif behavior.endswith("_exit"):
                        intruder_name = behavior[:-5]
                        if intruder_name not in intruders:
                            intruders[intruder_name] = {'enters': None, 'exit': None}
                        if intruders[intruder_name]['exit'] is not None:
                            return False, f"Multiple exits found for intruder '{intruder_name}'."
                        intruders[intruder_name]['exit'] = (start_frame, end_frame)
                    elif behavior.endswith("_exits"):
                        intruder_name = behavior[:-6]
                        if intruder_name not in intruders:
                            intruders[intruder_name] = {'enters': None, 'exit': None}
                        if intruders[intruder_name]['exit'] is not None:
                            return False, f"Multiple exits found for intruder '{intruder_name}'."
                        intruders[intruder_name]['exit'] = (start_frame, end_frame)

            intervals = []
            for name, data in intruders.items():
                if data['enters'] is None or data['exit'] is None:
                    return False, f"Missing enters or exit for intruder '{name}'."
                enters_start, _ = data['enters']
                _, exit_end = data['exit']
                clip_start = enters_start
                clip_end = exit_end
                if clip_end < clip_start:
                    return False, f"Exit occurs before enter for intruder '{name}'."
                intervals.append((clip_start, clip_end, name))

            intervals.sort(key=lambda x: x[0])
            for i in range(len(intervals) - 1):
                if intervals[i+1][0] <= intervals[i][1]:
                    return False, (
                        "Overlapping intruder intervals found between "
                        f"'{intervals[i][2]}' and '{intervals[i+1][2]}'."
                    )

            cap = cv2.VideoCapture(str(self.input_file))
            if not cap.isOpened():
                return False, f"Could not open {self.input_file} as .seq."

            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')

            for (clip_start, clip_end, intruder_name) in intervals:
                base_output = self.output_file.stem  # base name from output_file
                out_name = f"{base_output}_{intruder_name}_1{self.output_file.suffix}"
                if self.output_folder and self.output_folder_checkbox.isChecked():
                    out_path = Path(self.output_folder) / out_name
                else:
                    out_path = self.output_file.parent / out_name

                out_writer = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height))
                cap.set(cv2.CAP_PROP_POS_FRAMES, clip_start - 1)
                current_frame = clip_start
                while current_frame <= clip_end:
                    ret, frame = cap.read()
                    if not ret:
                        break
                    out_writer.write(frame)
                    current_frame += 1
                out_writer.release()

            cap.release()
            return True, f"Successfully clipped intruders for file {self.input_file.name}."
        except Exception as e:
            return False, str(e)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()