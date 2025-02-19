import sys
import os
import subprocess
import time
from pathlib import Path
import cv2
from PIL import Image
from pdf2image import convert_from_path
import pypandoc
from docx2pdf import convert as docx2pdf_convert
import csv

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QLabel, QVBoxLayout,
    QHBoxLayout, QComboBox, QFileDialog, QProgressBar, QMessageBox,
    QSizePolicy, QCheckBox, QInputDialog, QDialog, QSlider, QGroupBox,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QSplitter, QMenu
)
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QUrl, QTimer, QEvent
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

# -----------------------------------------------------------------------------
# Helper Function for Video Conversion (seq or mp4 to AVI)
# -----------------------------------------------------------------------------
def video_to_avi(input_path, avi_path):
    """
    Convert the input video (.seq or .mp4) to an AVI file using ffmpeg with the MJPEG codec.
    Forces AVI container, pixel format yuvj420p, 25 fps, and MJPG tag.
    """
    cmd = [
        'ffmpeg',
        '-i', str(input_path),
        '-c:v', 'mjpeg',
        '-qscale:v', '2',
        '-pix_fmt', 'yuvj420p',
        '-vtag', 'MJPG',
        '-r', '25',
        '-y',
        str(avi_path)
    ]
    process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if process.returncode != 0:
        return False, f"FFmpeg error: {process.stderr.decode('utf-8')}"
    time.sleep(1)
    if not avi_path.exists() or avi_path.stat().st_size < 1000:
        return False, f"Output AVI file {avi_path} seems empty or invalid."
    return True, f"Converted {input_path} to temporary AVI: {avi_path}"

# -----------------------------------------------------------------------------
# Conversion Thread for Non-Clipping Conversions
# -----------------------------------------------------------------------------
class ConversionThread(QThread):
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, input_file, output_file, conversion_type, parent=None):
        super().__init__(parent)
        self.input_file = Path(input_file)
        self.output_file = Path(output_file)
        self.conversion_type = conversion_type

    def run(self):
        try:
            success, msg = False, "Unknown conversion"
            if self.conversion_type == 'seq_to_mp4':
                success, msg = self.seq_to_mp4()
            elif self.conversion_type == 'seq_to_avi':
                success, msg = self.seq_to_avi()
            elif self.conversion_type == 'video_to_avi':
                success, msg = video_to_avi(self.input_file, self.output_file)
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
                success, msg = self.generic_conversion()
            self.finished_signal.emit(success, msg)
        except Exception as e:
            self.finished_signal.emit(False, str(e))

    def seq_to_mp4(self):
        cap = cv2.VideoCapture(str(self.input_file))
        if not cap.isOpened():
            return False, f"Could not open {self.input_file} as .seq."
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 25
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
            if total_frames > 0:
                progress_percent = int((frame_count / total_frames) * 100)
                self.progress_signal.emit(progress_percent)
        cap.release()
        out.release()
        return True, f"Converted .seq to .mp4: {self.output_file}"

    def seq_to_avi(self):
        cap = cv2.VideoCapture(str(self.input_file))
        if not cap.isOpened():
            return False, f"Could not open {self.input_file} as .seq."
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 25
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
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
        return True, f"Converted .seq to .avi: {self.output_file}"

    def ffmpeg_video_convert(self):
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
        return True, f"Video conversion to {self.output_file} completed."

    def image_to_image(self):
        try:
            img = Image.open(self.input_file)
            if img.mode in ["RGBA", "P"]:
                img = img.convert("RGB")
            img.save(self.output_file)
            return True, f"Image conversion to {self.output_file} completed."
        except Exception as e:
            return False, f"Image conversion failed: {str(e)}"

    def image_to_pdf(self):
        try:
            img = Image.open(self.input_file)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(self.output_file, "PDF")
            return True, f"Image -> PDF conversion to {self.output_file} completed."
        except Exception as e:
            return False, f"Image->PDF conversion failed: {str(e)}"

    def pdf_to_image(self):
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

    def pdf_to_docx(self):
        try:
            output = pypandoc.convert_file(str(self.input_file), 'docx', outputfile=str(self.output_file))
            if output:
                return False, f"pypandoc error: {output}"
            return True, f"PDF->DOCX conversion to {self.output_file} completed."
        except Exception as e:
            return False, f"PDF->DOCX failed: {str(e)}"

    def pdf_to_txt(self):
        try:
            output = pypandoc.convert_file(str(self.input_file), 'plain', outputfile=str(self.output_file))
            if output:
                return False, f"pypandoc error: {output}"
            return True, f"PDF->TXT conversion to {self.output_file} completed."
        except Exception as e:
            return False, f"PDF->TXT failed: {str(e)}"

    def docx_to_pdf(self):
        try:
            docx2pdf_convert(str(self.input_file), str(self.output_file))
            return True, f"DOCX->PDF conversion to {self.output_file} completed."
        except Exception as e:
            return False, f"DOCX->PDF failed: {str(e)}"

    def docx_to_txt(self):
        try:
            output = pypandoc.convert_file(str(self.input_file), 'plain', outputfile=str(self.output_file))
            if output:
                return False, f"pypandoc error: {output}"
            return True, f"DOCX->TXT conversion to {self.output_file} completed."
        except Exception as e:
            return False, f"DOCX->TXT failed: {str(e)}"

    def txt_to_pdf(self):
        try:
            output = pypandoc.convert_file(str(self.input_file), 'pdf', outputfile=str(self.output_file))
            if output:
                return False, f"pypandoc error: {output}"
            return True, f"TXT->PDF conversion to {self.output_file} completed."
        except Exception as e:
            return False, f"TXT->PDF failed: {str(e)}"

    def txt_to_docx(self):
        try:
            output = pypandoc.convert_file(str(self.input_file), 'docx', outputfile=str(self.output_file))
            if output:
                return False, f"pypandoc error: {output}"
            return True, f"TXT->DOCX conversion to {self.output_file} completed."
        except Exception as e:
            return False, f"TXT->DOCX failed: {str(e)}"

    def generic_conversion(self):
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

# -----------------------------------------------------------------------------
# Integrated Video Annotation Dialog (using Qt Multimedia)
# -----------------------------------------------------------------------------
class VideoAnnotationDialog(QDialog):
    def __init__(self, video_path, parent=None):
        super().__init__(parent)
        # Set standard window flags to include normal decorations (title bar, minimize, maximize)
        self.setWindowFlags(Qt.WindowType.Window)
        self.setWindowTitle("Video Annotation")
        self.video_path = str(video_path)
        self.annotations = {}  # { intruderName: {"enter": frame, "exit": frame} }
        
        cap = cv2.VideoCapture(self.video_path)
        self.fps = cap.get(cv2.CAP_PROP_FPS)
        if self.fps <= 0:
            self.fps = 25
        cap.release()
        
        self.cap_preview = cv2.VideoCapture(self.video_path)
        self.singleClickTimer = QTimer(self)
        self.singleClickTimer.setSingleShot(True)
        self.singleClickTimer.timeout.connect(self.perform_single_click)
        self.clicked_row = None
        self.clicked_column = None
        
        self.init_video_section()
        self.init_annotation_panel()
        self.setup_splitter()
        self.annotationTable.installEventFilter(self)
        initial_position = int(1000 / self.fps)
        self.mediaPlayer.setPosition(initial_position)

    def init_video_section(self):
        self.videoSection = QWidget(self)
        layout = QVBoxLayout(self.videoSection)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.mediaPlayer = QMediaPlayer(self)
        self.audioOutput = QAudioOutput(self)
        self.mediaPlayer.setAudioOutput(self.audioOutput)
        self.videoWidget = QVideoWidget(self)
        self.mediaPlayer.setVideoOutput(self.videoWidget)
        self.mediaPlayer.setSource(QUrl.fromLocalFile(self.video_path))

        self.previewLabel = QLabel(self)
        self.previewLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.previewLabel.setMinimumHeight(100)
        self.previewLabel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.positionSlider = QSlider(Qt.Orientation.Horizontal, self)
        self.positionSlider.setRange(0, 0)
        self.positionSlider.sliderMoved.connect(self.set_position)
        self.positionSlider.sliderReleased.connect(self.slider_released)
        self.mediaPlayer.positionChanged.connect(self.position_changed)
        self.mediaPlayer.durationChanged.connect(self.duration_changed)

        self.playButton = QPushButton("Play", self)
        self.playButton.clicked.connect(self.toggle_play)
        self.markEnterButton = QPushButton("Mark Enter", self)
        self.markEnterButton.clicked.connect(self.mark_enter)
        self.markExitButton = QPushButton("Mark Exit", self)
        self.markExitButton.clicked.connect(self.mark_exit)
        self.doneButton = QPushButton("Done", self)
        self.doneButton.clicked.connect(self.accept)

        self.frameLabel = QLabel("Frame: 1", self)

        self.scrubStepCombo = QComboBox(self)
        self.scrubStepCombo.addItems(["1", "10", "100", "1000"])
        self.scrubStepCombo.setCurrentIndex(0)
        scrubLayout = QHBoxLayout()
        scrubLayout.addWidget(QLabel("Scrub Step:", self))
        scrubLayout.addWidget(self.scrubStepCombo)
        scrubLayout.addStretch()

        controlLayout = QHBoxLayout()
        controlLayout.addWidget(self.playButton)
        controlLayout.addWidget(self.markEnterButton)
        controlLayout.addWidget(self.markExitButton)
        controlLayout.addWidget(self.doneButton)

        layout.addWidget(self.videoWidget)
        layout.addWidget(self.previewLabel)
        layout.addWidget(self.positionSlider)
        layout.addLayout(scrubLayout)
        layout.addWidget(self.frameLabel)
        layout.addLayout(controlLayout)

    def init_annotation_panel(self):
        self.annotationGroup = QGroupBox("Annotations", self)
        annLayout = QVBoxLayout(self.annotationGroup)
        annLayout.setContentsMargins(5, 5, 5, 5)

        btnLayout = QHBoxLayout()
        self.importCSVButton = QPushButton("Import CSV", self)
        self.importCSVButton.clicked.connect(self.import_csv_annotations)
        self.clearAnnotationsButton = QPushButton("Clear Annotations", self)
        self.clearAnnotationsButton.clicked.connect(self.clear_annotations)
        btnLayout.addWidget(self.importCSVButton)
        btnLayout.addWidget(self.clearAnnotationsButton)
        btnLayout.addStretch()
        annLayout.addLayout(btnLayout)

        self.annotationTable = QTableWidget(self)
        self.annotationTable.setColumnCount(3)
        self.annotationTable.setHorizontalHeaderLabels(["Intruder", "Enter", "Exit"])
        self.annotationTable.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.annotationTable.cellClicked.connect(self.on_cell_clicked)
        self.annotationTable.cellDoubleClicked.connect(self.on_cell_double_clicked)
        self.annotationTable.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.annotationTable.customContextMenuRequested.connect(self.show_context_menu)
        self.annotationTable.itemChanged.connect(self.table_item_changed)
        annLayout.addWidget(self.annotationTable)

        self.refresh_annotation_table()

    def setup_splitter(self):
        splitter = QSplitter(Qt.Orientation.Vertical, self)
        splitter.addWidget(self.videoSection)
        splitter.addWidget(self.annotationGroup)
        splitter.setSizes([400, 200])
        splitter.setChildrenCollapsible(False)
        mainLayout = QVBoxLayout(self)
        mainLayout.addWidget(splitter)
        self.setLayout(mainLayout)

    def on_cell_clicked(self, row, column):
        self.clicked_row = row
        self.clicked_column = column
        self.singleClickTimer.start(250)

    def on_cell_double_clicked(self, row, column):
        if self.singleClickTimer.isActive():
            self.singleClickTimer.stop()

    def perform_single_click(self):
        if self.clicked_column in [1, 2]:
            item = self.annotationTable.item(self.clicked_row, self.clicked_column)
            try:
                frame = int(item.text())
                frame_ms = int((frame - 1) * (1000 / self.fps))
                self.mediaPlayer.setPosition(frame_ms)
            except ValueError:
                pass

    def show_context_menu(self, pos):
        index = self.annotationTable.indexAt(pos)
        if not index.isValid():
            return
        row = index.row()
        menu = QMenu(self)
        duplicate_action = menu.addAction("Duplicate")
        delete_action = menu.addAction("Delete")
        action = menu.exec(self.annotationTable.viewport().mapToGlobal(pos))
        intruder = self.annotationTable.item(row, 0).text()
        if action == duplicate_action:
            original = self.annotations.get(intruder)
            new_intruder = intruder + "_copy"
            copy_index = 1
            while new_intruder in self.annotations:
                copy_index += 1
                new_intruder = f"{intruder}_copy{copy_index}"
            self.annotations[new_intruder] = {"enter": original["enter"], "exit": original["exit"]}
            self.refresh_annotation_table()
        elif action == delete_action:
            if intruder in self.annotations:
                del self.annotations[intruder]
                self.refresh_annotation_table()

    def eventFilter(self, source, event):
        if source is self.annotationTable and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Delete:
                selected_rows = {item.row() for item in self.annotationTable.selectedItems()}
                for row in sorted(selected_rows, reverse=True):
                    intruder = self.annotationTable.item(row, 0).text()
                    if intruder in self.annotations:
                        del self.annotations[intruder]
                self.refresh_annotation_table()
                return True
        return super().eventFilter(source, event)

    def import_csv_annotations(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Import CSV Annotations", "", "CSV Files (*.csv)")
        if not fileName:
            return
        try:
            with open(fileName, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                expected_headers = ["intruder", "enter", "exit"]
                missing = [h for h in expected_headers if h not in reader.fieldnames]
                if missing:
                    QMessageBox.critical(self, "CSV Error", f"Missing header(s): {', '.join(missing)}")
                    return
                csv_annotations = {}
                for row in reader:
                    intruder = row["intruder"]
                    enter = int(row["enter"])
                    exit_frame = int(row["exit"])
                    csv_annotations[intruder] = {"enter": enter, "exit": exit_frame}
        except Exception as e:
            QMessageBox.critical(self, "CSV Error", f"Error reading CSV: {str(e)}")
            return

        reply = QMessageBox.question(
            self,
            "Merge or Replace",
            "Do you want to merge with existing annotations? (Selecting No will replace them)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.No:
            self.annotations = {}
        self.annotations.update(csv_annotations)
        self.refresh_annotation_table()
        QMessageBox.information(self, "CSV Imported", "CSV annotations imported successfully.")

    def clear_annotations(self):
        self.annotations = {}
        self.refresh_annotation_table()

    def refresh_annotation_table(self):
        self.annotationTable.blockSignals(True)
        self.annotationTable.setRowCount(0)
        for i, (intruder, data) in enumerate(self.annotations.items()):
            self.annotationTable.insertRow(i)
            intruder_item = QTableWidgetItem(intruder)
            intruder_item.setFlags(intruder_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.annotationTable.setItem(i, 0, intruder_item)
            enter_item = QTableWidgetItem(str(data.get("enter", "")))
            self.annotationTable.setItem(i, 1, enter_item)
            exit_item = QTableWidgetItem(str(data.get("exit", "")))
            self.annotationTable.setItem(i, 2, exit_item)
        self.annotationTable.blockSignals(False)

    def table_item_changed(self, item):
        row = item.row()
        intruder_item = self.annotationTable.item(row, 0)
        if not intruder_item:
            return
        intruder = intruder_item.text()
        try:
            enter = int(self.annotationTable.item(row, 1).text())
            exit_val = int(self.annotationTable.item(row, 2).text())
        except (ValueError, AttributeError):
            return
        self.annotations[intruder] = {"enter": enter, "exit": exit_val}

    def toggle_play(self):
        if self.mediaPlayer.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.mediaPlayer.pause()
            self.playButton.setText("Play")
        else:
            self.mediaPlayer.play()
            self.playButton.setText("Pause")

    def position_changed(self, position):
        self.positionSlider.setValue(position)
        frame = int(position / 1000.0 * self.fps) + 1
        self.frameLabel.setText(f"Frame: {frame if frame > 0 else 1}")
        self.update_preview()

    def duration_changed(self, duration):
        self.positionSlider.setRange(0, duration)
        self.positionSlider.setSingleStep(int(1000 / self.fps))

    def set_position(self, position):
        self.mediaPlayer.setPosition(position)

    def slider_released(self):
        pos = self.positionSlider.value()
        frame_ms = int(1000 / self.fps)
        rounded = round(pos / frame_ms) * frame_ms
        self.mediaPlayer.setPosition(rounded)

    def update_preview(self):
        position = self.mediaPlayer.position()
        self.cap_preview.set(cv2.CAP_PROP_POS_MSEC, position)
        ret, frame = self.cap_preview.read()
        if ret:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            height, width, channel = frame_rgb.shape
            bytes_per_line = channel * width
            qimg = QImage(frame_rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg).scaled(
                self.previewLabel.width(), self.previewLabel.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.previewLabel.setPixmap(pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_preview()
    
    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self.update_preview)

    def keyPressEvent(self, event):
        try:
            step = int(self.scrubStepCombo.currentText())
        except ValueError:
            step = 1
        frame_ms = int(1000 / self.fps)
        increment = step * frame_ms
        if event.key() == Qt.Key.Key_Left:
            newPos = max(0, self.mediaPlayer.position() - increment)
            self.mediaPlayer.setPosition(newPos)
        elif event.key() == Qt.Key.Key_Right:
            newPos = self.mediaPlayer.position() + increment
            self.mediaPlayer.setPosition(newPos)
        else:
            super().keyPressEvent(event)

    def mark_enter(self):
        current_position = self.mediaPlayer.position()
        frame = int(current_position / 1000.0 * self.fps) + 1
        frame = frame if frame > 0 else 1
        intruder_name, ok = QInputDialog.getText(self, "Intruder Name", "Enter intruder name for entry:")
        if ok and intruder_name:
            if intruder_name in self.annotations and "enter" in self.annotations[intruder_name]:
                QMessageBox.warning(self, "Warning", f"Enter already marked for {intruder_name}.")
            else:
                if intruder_name not in self.annotations:
                    self.annotations[intruder_name] = {}
                self.annotations[intruder_name]["enter"] = frame
                QMessageBox.information(self, "Annotation", f"Marked enter for {intruder_name} at frame {frame}.")
                self.refresh_annotation_table()

    def mark_exit(self):
        current_position = self.mediaPlayer.position()
        frame = int(current_position / 1000.0 * self.fps) + 1
        frame = frame if frame > 0 else 1
        available = [name for name, data in self.annotations.items() if "enter" in data and "exit" not in data]
        if available:
            intruder_name, ok = QInputDialog.getItem(self, "Select Intruder",
                                                     "Select intruder for exit:", available, 0, False)
        else:
            intruder_name, ok = QInputDialog.getText(self, "Intruder Name", "Enter intruder name for exit:")
        if ok and intruder_name:
            if intruder_name in self.annotations and "exit" in self.annotations[intruder_name]:
                QMessageBox.warning(self, "Warning", f"Exit already marked for {intruder_name}.")
            else:
                if intruder_name not in self.annotations:
                    self.annotations[intruder_name] = {}
                self.annotations[intruder_name]["exit"] = frame
                QMessageBox.information(self, "Annotation", f"Marked exit for {intruder_name} at frame {frame}.")
                self.refresh_annotation_table()

    def closeEvent(self, event):
        if self.cap_preview.isOpened():
            self.cap_preview.release()
        event.accept()

    # Standard window decorations now provide a full screen/maximize button.
    def toggle_full_screen(self):
        if self.windowState() & Qt.WindowState.WindowFullScreen:
            self.setWindowState(Qt.WindowState.WindowNoState)
        else:
            self.setWindowState(Qt.WindowState.WindowFullScreen)

# -----------------------------------------------------------------------------
# MainWindow (File Converter & Video Annotator)
# -----------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Multi-Format File Converter & Video Annotator")
        self.resize(900, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Banner
        banner_layout = QHBoxLayout()
        self.logo_label = QLabel()
        logo_path = os.path.join('media', 'nih_logo.png')
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            self.logo_label.setPixmap(pixmap.scaledToHeight(50, Qt.TransformationMode.SmoothTransformation))
        banner_layout.addWidget(self.logo_label)
        banner_label = QLabel("Multi-Format File Converter & Video Annotator")
        banner_label.setStyleSheet("font-size: 24px; font-weight: bold; color: white;")
        banner_layout.addWidget(banner_label)
        banner_layout.addStretch()
        banner_widget = QWidget()
        banner_widget.setLayout(banner_layout)
        banner_widget.setStyleSheet("background-color: #205493;")
        main_layout.addWidget(banner_widget, 1)

        # Bottom container
        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)

        file_layout = QHBoxLayout()
        self.file_label = QLabel("No file selected")
        self.select_file_button = QPushButton("Select File")
        self.select_file_button.clicked.connect(self.select_file)
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(self.select_file_button)
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
        self.output_folder_checkbox.stateChanged.connect(self.toggle_output_folder_button)

        annotation_layout = QHBoxLayout()
        self.clip_checkbox = QCheckBox("Clip using Annotation")
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

        output_layout = QHBoxLayout()
        self.output_label = QLabel("Output Format:")
        self.output_combo = QComboBox()
        self.output_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
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
        bottom_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
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

        self.OUTPUT_FORMATS = {
            ".seq":  [".mp4", ".avi"],
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
        self.setStyleSheet("QMainWindow { background-color: #FFFFFF; }")

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

    def select_file(self):
        file_dialog = QFileDialog()
        if self.multiple_files_checkbox.isChecked():
            file_paths, _ = file_dialog.getOpenFileNames(self, "Select files to convert")
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

    def update_output_options(self):
        self.output_combo.clear()
        if self.current_extension in self.OUTPUT_FORMATS:
            self.output_combo.addItems(self.OUTPUT_FORMATS[self.current_extension])
        else:
            self.output_combo.addItem(".mp4")

    def select_annotation_file(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(self, "Select Annotation File", filter="Text Files (*.txt)")
        if file_path:
            self.annotation_file = Path(file_path)
            self.annotation_file_label.setText(self.annotation_file.name)

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

            if self.clip_checkbox.isChecked():
                if self.current_extension not in [".seq", ".mp4"]:
                    QMessageBox.critical(
                        self,
                        "Error",
                        "Clipped output is only supported for .seq or .mp4 input in this example."
                    )
                    self.convert_button.setEnabled(True)
                    self.select_file_button.setEnabled(True)
                    return
                if output_ext == ".gif":
                    QMessageBox.critical(
                        self,
                        "Error",
                        "GIF output is not supported for clipping."
                    )
                    self.convert_button.setEnabled(True)
                    self.select_file_button.setEnabled(True)
                    return
                if self.current_extension == ".seq":
                    self.temp_avi_file = self.input_file.parent / (self.input_file.stem + "_temp.avi")
                    success, message = video_to_avi(self.input_file, self.temp_avi_file)
                    if not success:
                        QMessageBox.critical(self, "Error", message)
                        self.convert_button.setEnabled(True)
                        self.select_file_button.setEnabled(True)
                        return
                else:
                    self.temp_avi_file = self.input_file

                annot_dialog = VideoAnnotationDialog(self.temp_avi_file)
                if annot_dialog.exec() == QDialog.DialogCode.Accepted:
                    annotations = annot_dialog.annotations
                    success, message = self.clip_by_annotations(annotations, self.temp_avi_file)
                    if success:
                        QMessageBox.information(self, "Success", message)
                    else:
                        QMessageBox.critical(self, "Error", message)
                else:
                    QMessageBox.warning(self, "Annotation", "Annotation cancelled.")

                try:
                    if self.current_extension == ".seq" and self.temp_avi_file.exists():
                        os.remove(self.temp_avi_file)
                except Exception:
                    pass

                self.current_file_index += 1
                self.progress_bar.setValue(0)
                self.process_next_file()
                return

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

    def clip_by_annotations(self, annotations, video_path):
        intervals = []
        for intruder, data in annotations.items():
            if "enter" not in data or "exit" not in data:
                return False, f"Incomplete annotation for intruder '{intruder}'."
            enter_frame = data["enter"]
            exit_frame = data["exit"] - 1
            if exit_frame < enter_frame:
                return False, f"Exit frame occurs before enter frame for intruder '{intruder}'."
            intervals.append((enter_frame, exit_frame, intruder))
        
        intervals.sort(key=lambda x: x[0])
        for i in range(len(intervals) - 1):
            if intervals[i+1][0] <= intervals[i][1]:
                return False, (
                    "Overlapping intruder intervals found between "
                    f"'{intervals[i][2]}' and '{intervals[i+1][2]}'."
                )
        
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
        for (enter_frame, exit_frame, intruder) in intervals:
            output_name = f"{self.output_file.stem}_{intruder}intruder{self.output_file.suffix}"
            if self.output_folder and self.output_folder_checkbox.isChecked():
                out_path = Path(self.output_folder) / output_name
            else:
                out_path = self.output_file.parent / output_name
            out_writer = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height))
            cap.set(cv2.CAP_PROP_POS_FRAMES, enter_frame - 1)
            while True:
                # Get the next frame index (0-indexed)
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

    def keyPressEvent(self, event):
        super().keyPressEvent(event)

# -----------------------------------------------------------------------------
# Main Function
# -----------------------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
