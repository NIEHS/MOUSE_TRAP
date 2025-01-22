"""
Neurobehavioral Circuits Group Multi-Format File Converter (Full Code)
----------------------------------------------------------------------
This single-file PyQt6 application contains code for
converting various file types (videos, images, PDFs, DOCX, TXT, etc.),
including .seq -> .mp4 (via OpenCV) and a fallback "generic_conversion"
using ffmpeg if needed.
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
    QSizePolicy
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
            # If needed, convert mode (e.g., RGBA -> RGB)
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
        We will save multiple images if the PDF has multiple pages, named
        <output_stem>_page{i}.<ext>.
        """
        try:
            base_name = self.output_file.stem
            out_dir = self.output_file.parent
            out_ext = self.output_file.suffix  # e.g., ".png"

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
        pypandoc.convert_file returns an empty string on success or an error string on failure.
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
        Convert PDF to plain text using pypandoc + pandoc.
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
        Note: This may require Microsoft Word on Windows/Mac or fallback with LibreOffice.
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
        Convert a text file into PDF via pypandoc (requires pandoc).
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
            '-y',  # overwrite
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

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # ----------------------------------------------------------------------
        # NIH-Like Banner
        # ----------------------------------------------------------------------
        banner_layout = QHBoxLayout()
        self.logo_label = QLabel()
        # If you have a local NIH logo, specify path here:
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
        banner_widget.setStyleSheet("background-color: #205493;")  # NIH-like color
        banner_widget.setLayout(banner_layout)
        main_layout.addWidget(banner_widget)

        # ----------------------------------------------------------------------
        # File Selection
        # ----------------------------------------------------------------------
        file_layout = QHBoxLayout()
        self.file_label = QLabel("No file selected")
        self.select_file_button = QPushButton("Select File")
        self.select_file_button.clicked.connect(self.select_file)

        file_layout.addWidget(self.file_label)
        file_layout.addWidget(self.select_file_button)
        main_layout.addLayout(file_layout)

        # ----------------------------------------------------------------------
        # Output Format
        # ----------------------------------------------------------------------
        output_layout = QHBoxLayout()
        self.output_label = QLabel("Output Format:")
        self.output_combo = QComboBox()
        self.output_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        output_layout.addWidget(self.output_label)
        output_layout.addWidget(self.output_combo)
        output_layout.addStretch()

        main_layout.addLayout(output_layout)

        # ----------------------------------------------------------------------
        # Convert Button + Progress
        # ----------------------------------------------------------------------
        self.convert_button = QPushButton("Convert")
        self.convert_button.clicked.connect(self.start_conversion)
        main_layout.addWidget(self.convert_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)

        # ----------------------------------------------------------------------
        # Internal State
        # ----------------------------------------------------------------------
        self.input_file = None
        self.output_file = None
        self.current_extension = None

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
        self.setStyleSheet("""
            QMainWindow {
                background-color: #FFFFFF;
            }
        """)

    def select_file(self):
        file_dialog = QFileDialog()
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
            # Fallback
            self.output_combo.addItem(".mp4")

    def start_conversion(self):
        if not self.input_file:
            QMessageBox.warning(self, "Warning", "No input file selected.")
            return

        output_ext = self.output_combo.currentText()
        self.output_file = self.input_file.with_suffix(output_ext)

        # Determine conversion type
        conversion_type = self.determine_conversion_type(self.current_extension, output_ext)

        # Setup thread
        self.thread = ConversionThread(
            input_file=self.input_file,
            output_file=self.output_file,
            conversion_type=conversion_type
        )
        self.thread.progress_signal.connect(self.update_progress)
        self.thread.finished_signal.connect(self.on_conversion_finished)

        # Disable UI while converting
        self.convert_button.setEnabled(False)
        self.select_file_button.setEnabled(False)

        self.thread.start()

    def determine_conversion_type(self, input_ext, output_ext):
        """
        Decide which conversion method to invoke based on input/output extension.
        """
        # .seq -> .mp4
        if input_ext == ".seq" and output_ext == ".mp4":
            return "seq_to_mp4"

        # Video -> Video
        video_exts = [".mp4", ".avi", ".mov", ".mkv", ".gif"]
        if input_ext in video_exts and output_ext in video_exts:
            return "video_to_video"

        # Image -> Image
        image_exts = [".jpg", ".jpeg", ".png", ".tiff", ".bmp"]
        if input_ext in image_exts and output_ext in image_exts:
            return "image_to_image"

        # Image -> PDF
        if input_ext in image_exts and output_ext == ".pdf":
            return "image_to_pdf"

        # PDF -> Image
        if input_ext == ".pdf" and output_ext in image_exts:
            return "pdf_to_image"

        # PDF -> DOCX
        if input_ext == ".pdf" and output_ext == ".docx":
            return "pdf_to_docx"

        # PDF -> TXT
        if input_ext == ".pdf" and output_ext == ".txt":
            return "pdf_to_txt"

        # DOCX -> PDF
        if input_ext == ".docx" and output_ext == ".pdf":
            return "docx_to_pdf"

        # DOCX -> TXT
        if input_ext == ".docx" and output_ext == ".txt":
            return "docx_to_txt"

        # TXT -> PDF
        if input_ext == ".txt" and output_ext == ".pdf":
            return "txt_to_pdf"

        # TXT -> DOCX
        if input_ext == ".txt" and output_ext == ".docx":
            return "txt_to_docx"

        # Fallback
        return "generic_conversion"

    @pyqtSlot(int)
    def update_progress(self, value):
        self.progress_bar.setValue(value)

    @pyqtSlot(bool, str)
    def on_conversion_finished(self, success, message):
        self.convert_button.setEnabled(True)
        self.select_file_button.setEnabled(True)
        self.progress_bar.setValue(100 if success else 0)

        if success:
            QMessageBox.information(self, "Success", message)
        else:
            QMessageBox.critical(self, "Error", message)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
