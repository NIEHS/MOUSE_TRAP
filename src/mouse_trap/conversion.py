"""Conversion helpers and worker thread for videos, images, PDFs, DOCX, and TXT."""

import subprocess
from pathlib import Path

import cv2
import pypandoc
from docx2pdf import convert as docx2pdf_convert
from pdf2image import convert_from_path
from PIL import Image
from PyQt6.QtCore import QProcess, QThread, pyqtSignal
from typing import Optional, Tuple, Union


# -----------------------------------------------------------------------------
# Helper Function for Video Conversion (seq or mp4 to AVI)
# -----------------------------------------------------------------------------
def video_to_avi(
    input_path: Union[Path, str], avi_path: Union[Path, str]
) -> Tuple[bool, str]:
    """Convert a video/sequence to MJPEG AVI using ffmpeg; returns (success, message)."""
    cmd = [
        "ffmpeg",
        "-i",
        str(input_path),
        "-c:v",
        "mjpeg",
        "-qscale:v",
        "2",
        "-pix_fmt",
        "yuvj420p",
        "-vtag",
        "MJPG",
        "-r",
        "25",
        "-y",
        str(avi_path),
    ]
    process = QProcess()
    process.start(cmd[0], cmd[1:])
    process.waitForFinished(-1)
    if process.exitCode() != 0:
        error_output = process.readAllStandardError().data().decode()
        return False, f"FFmpeg error: {error_output}"

    if not Path(avi_path).exists() or Path(avi_path).stat().st_size < 1000:
        return False, f"Output AVI file {avi_path} seems empty or invalid."
    return True, f"Converted {input_path} to temporary AVI: {avi_path}"


# -----------------------------------------------------------------------------
# Conversion Thread for Non-Clipping Conversions
# -----------------------------------------------------------------------------
class ConversionThread(QThread):
    """Run a long-running conversion in a worker thread."""

    #: Emitted with an integer percentage of overall progress (0-100).
    progress_signal = pyqtSignal(int)

    #: Emitted when conversion finishes. Arguments: (success, message).
    finished_signal = pyqtSignal(bool, str)

    def __init__(
        self,
        input_file: Union[Path, str],
        output_file: Union[Path, str],
        conversion_type: str,
        parent: Optional[object] = None,
    ) -> None:
        """Store input/output paths and selected conversion type."""
        super().__init__(parent)
        self.input_file = Path(input_file)
        self.output_file = Path(output_file)
        self.conversion_type = conversion_type
        self.total_duration_ms = None  # Only used for ffmpeg conversions if needed

    def run(self) -> None:
        """Dispatch to the selected conversion routine and emit result signals."""
        try:
            success, msg = False, "Unknown conversion"
            if self.conversion_type == "seq_to_mp4":
                success, msg = self.seq_to_mp4()
            elif self.conversion_type == "seq_to_avi":
                success, msg = video_to_avi(self.input_file, self.output_file)
            elif self.conversion_type == "video_to_avi":
                success, msg = video_to_avi(self.input_file, self.output_file)
            elif self.conversion_type == "video_to_video":
                success, msg = self.ffmpeg_video_convert()
            elif self.conversion_type == "image_to_image":
                success, msg = self.image_to_image()
            elif self.conversion_type == "image_to_pdf":
                success, msg = self.image_to_pdf()
            elif self.conversion_type == "pdf_to_image":
                success, msg = self.pdf_to_image()
            elif self.conversion_type == "pdf_to_docx":
                success, msg = self.pdf_to_docx()
            elif self.conversion_type == "pdf_to_txt":
                success, msg = self.pdf_to_txt()
            elif self.conversion_type == "docx_to_pdf":
                success, msg = self.docx_to_pdf()
            elif self.conversion_type == "docx_to_txt":
                success, msg = self.docx_to_txt()
            elif self.conversion_type == "txt_to_pdf":
                success, msg = self.txt_to_pdf()
            elif self.conversion_type == "txt_to_docx":
                success, msg = self.txt_to_docx()
            else:
                success, msg = self.generic_conversion()
            self.finished_signal.emit(success, msg)
        except Exception as e:
            self.finished_signal.emit(False, str(e))

    def seq_to_mp4(self) -> Tuple[bool, str]:
        """Transcode .seq frames to .mp4 via OpenCV, emitting progress."""
        cap = cv2.VideoCapture(str(self.input_file))
        if not cap.isOpened():
            return False, f"Could not open {self.input_file} as .seq."
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 25
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(str(self.output_file), fourcc, fps, (width, height))
        frame_count = 0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            out.write(frame)
            frame_count += 1
            if total_frames > 0:
                progress_percent = int((frame_count / total_frames) * 100)
                self.progress_signal.emit(progress_percent)
        cap.release()
        out.release()
        return True, f"Converted .seq to .mp4: {self.output_file}"

    def ffmpeg_video_convert(self) -> Tuple[bool, str]:
        """Transcode between video formats via ffmpeg, reporting progress."""
        process = QProcess()
        cmd = [
            "ffmpeg",
            "-i",
            str(self.input_file),
            "-progress",
            "pipe:1",
            "-y",
            str(self.output_file),
        ]
        process.setProgram(cmd[0])
        process.setArguments(cmd[1:])
        process.readyReadStandardOutput.connect(
            lambda: self.handle_ffmpeg_output(process)
        )
        process.start()
        process.waitForFinished(-1)
        if (
            process.exitStatus() == QProcess.ExitStatus.NormalExit
            and process.exitCode() == 0
        ):
            return True, f"Video conversion to {self.output_file} completed."
        else:
            return False, "FFmpeg conversion failed."

    def handle_ffmpeg_output(self, process: QProcess) -> None:
        """Parse ffmpeg -progress output and emit percent complete."""
        output = process.readAllStandardOutput().data().decode()
        for line in output.splitlines():
            if line.startswith("out_time_ms="):
                try:
                    out_time_ms = int(line.split("=")[1])
                    if self.total_duration_ms:
                        percent = int((out_time_ms / self.total_duration_ms) * 100)
                        self.progress_signal.emit(percent)
                except Exception:
                    pass

    def image_to_image(self) -> Tuple[bool, str]:
        """Convert between common image formats using Pillow."""
        try:
            img = Image.open(self.input_file)
            if img.mode in ["RGBA", "P"]:
                img = img.convert("RGB")
            img.save(self.output_file)
            return True, f"Image conversion to {self.output_file} completed."
        except Exception as e:
            return False, f"Image conversion failed: {str(e)}"

    def image_to_pdf(self) -> Tuple[bool, str]:
        """Write the input image as a single-page PDF."""
        try:
            img = Image.open(self.input_file)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(self.output_file, "PDF")
            return True, f"Image -> PDF conversion to {self.output_file} completed."
        except Exception as e:
            return False, f"Image->PDF conversion failed: {str(e)}"

    def pdf_to_image(self) -> Tuple[bool, str]:
        """Export each PDF page as an image file in the target directory."""
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

    def pdf_to_docx(self) -> Tuple[bool, str]:
        """Convert PDF to DOCX via pypandoc."""
        try:
            output = pypandoc.convert_file(
                str(self.input_file), "docx", outputfile=str(self.output_file)
            )
            if output:
                return False, f"pypandoc error: {output}"
            return True, f"PDF->DOCX conversion to {self.output_file} completed."
        except Exception as e:
            return False, f"PDF->DOCX failed: {str(e)}"

    def pdf_to_txt(self) -> Tuple[bool, str]:
        """Extract text from PDF to a .txt via pypandoc."""
        try:
            output = pypandoc.convert_file(
                str(self.input_file), "plain", outputfile=str(self.output_file)
            )
            if output:
                return False, f"pypandoc error: {output}"
            return True, f"PDF->TXT conversion to {self.output_file} completed."
        except Exception as e:
            return False, f"PDF->TXT failed: {str(e)}"

    def docx_to_pdf(self) -> Tuple[bool, str]:
        """Convert a DOCX document to PDF."""
        try:
            docx2pdf_convert(str(self.input_file), str(self.output_file))
            return True, f"DOCX->PDF conversion to {self.output_file} completed."
        except Exception as e:
            return False, f"DOCX->PDF failed: {str(e)}"

    def docx_to_txt(self) -> Tuple[bool, str]:
        """Convert a DOCX document to plain text."""
        try:
            output = pypandoc.convert_file(
                str(self.input_file), "plain", outputfile=str(self.output_file)
            )
            if output:
                return False, f"pypandoc error: {output}"
            return True, f"DOCX->TXT conversion to {self.output_file} completed."
        except Exception as e:
            return False, f"DOCX->TXT failed: {str(e)}"

    def txt_to_pdf(self) -> Tuple[bool, str]:
        """Convert a plain-text file to PDF."""
        try:
            output = pypandoc.convert_file(
                str(self.input_file), "pdf", outputfile=str(self.output_file)
            )
            if output:
                return False, f"pypandoc error: {output}"
            return True, f"TXT->PDF conversion to {self.output_file} completed."
        except Exception as e:
            return False, f"TXT->PDF failed: {str(e)}"

    def txt_to_docx(self) -> Tuple[bool, str]:
        """Convert a plain-text file to DOCX."""
        try:
            output = pypandoc.convert_file(
                str(self.input_file), "docx", outputfile=str(self.output_file)
            )
            if output:
                return False, f"pypandoc error: {output}"
            return True, f"TXT->DOCX conversion to {self.output_file} completed."
        except Exception as e:
            return False, f"TXT->DOCX failed: {str(e)}"

    def generic_conversion(self) -> Tuple[bool, str]:
        """Fallback ffmpeg path when no specialized converter applies."""
        cmd = ["ffmpeg", "-i", str(self.input_file), "-y", str(self.output_file)]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, stderr = process.communicate()
        if process.returncode != 0:
            return False, f"FFmpeg error: {stderr.decode('utf-8')}"
        return True, f"Generic conversion to {self.output_file} completed."
