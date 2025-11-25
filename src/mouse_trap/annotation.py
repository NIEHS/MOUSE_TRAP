import csv

import cv2
from PyQt6.QtCore import QEvent, QTimer, Qt, QUrl
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


# -----------------------------------------------------------------------------
# Integrated Video Annotation Dialog (using Qt Multimedia)
# -----------------------------------------------------------------------------
class VideoAnnotationDialog(QDialog):
    def __init__(self, video_path, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Window)
        self.setWindowTitle("Video Annotation")
        self.video_path = str(video_path)
        self.annotations = {}  # { intruderName: {"enter": frame, "exit": frame} }

        cap = cv2.VideoCapture(self.video_path)
        self.fps = cap.get(cv2.CAP_PROP_FPS)
        if self.fps <= 0:
            self.fps = 25
        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
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
        self.previewLabel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

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
        self.importCSVButton.clicked.connect(self.import_csv_annotations_multi)
        self.clearAnnotationsButton = QPushButton("Clear Annotations", self)
        self.clearAnnotationsButton.clicked.connect(self.clear_annotations)
        btnLayout.addWidget(self.importCSVButton)
        btnLayout.addWidget(self.clearAnnotationsButton)
        btnLayout.addStretch()
        annLayout.addLayout(btnLayout)

        self.annotationTable = QTableWidget(self)
        self.annotationTable.setColumnCount(3)
        self.annotationTable.setHorizontalHeaderLabels(["Intruder", "Enter", "Exit"])
        self.annotationTable.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
        )
        self.annotationTable.cellClicked.connect(self.on_cell_clicked)
        self.annotationTable.cellDoubleClicked.connect(self.on_cell_double_clicked)
        self.annotationTable.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
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
            self.annotations[new_intruder] = {
                "enter": original["enter"],
                "exit": original["exit"],
            }
            self.refresh_annotation_table()
        elif action == delete_action:
            if intruder in self.annotations:
                del self.annotations[intruder]
                self.refresh_annotation_table()

    def eventFilter(self, source, event):
        if source is self.annotationTable and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Delete:
                selected_rows = {
                    item.row() for item in self.annotationTable.selectedItems()
                }
                for row in sorted(selected_rows, reverse=True):
                    intruder = self.annotationTable.item(row, 0).text()
                    if intruder in self.annotations:
                        del self.annotations[intruder]
                self.refresh_annotation_table()
                return True
        return super().eventFilter(source, event)

    def import_csv_annotations_multi(self):
        fileName, _ = QFileDialog.getOpenFileName(
            self, "Import CSV Annotations for Multiple Files", "", "CSV Files (*.csv)"
        )
        if not fileName:
            return
        mapping = {}
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
        frame = min(int(position / 1000.0 * self.fps) + 1, self.total_frames)
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
        QTimer.singleShot(150, self.update_preview)

    def update_preview(self):
        position = self.mediaPlayer.position()
        self.cap_preview.set(cv2.CAP_PROP_POS_MSEC, position)
        ret, frame = self.cap_preview.read()
        if ret:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            height, width, channel = frame_rgb.shape
            bytes_per_line = channel * width
            qimg = QImage(
                frame_rgb.data,
                width,
                height,
                bytes_per_line,
                QImage.Format.Format_RGB888,
            )
            pixmap = QPixmap.fromImage(qimg).scaled(
                self.previewLabel.width(),
                self.previewLabel.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
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
        frame = min(int(current_position / 1000.0 * self.fps) + 1, self.total_frames)
        intruder_name, ok = QInputDialog.getText(
            self, "Intruder Name", "Enter intruder name for entry:"
        )
        if ok and intruder_name:
            if (
                intruder_name in self.annotations
                and "enter" in self.annotations[intruder_name]
            ):
                QMessageBox.warning(
                    self, "Warning", f"Enter already marked for {intruder_name}."
                )
            else:
                if intruder_name not in self.annotations:
                    self.annotations[intruder_name] = {}
                self.annotations[intruder_name]["enter"] = frame
                QMessageBox.information(
                    self,
                    "Annotation",
                    f"Marked enter for {intruder_name} at frame {frame}.",
                )
                self.refresh_annotation_table()

    def mark_exit(self):
        current_position = self.mediaPlayer.position()
        frame = min(int(current_position / 1000.0 * self.fps) + 1, self.total_frames)
        available = [
            name
            for name, data in self.annotations.items()
            if "enter" in data and "exit" not in data
        ]
        if available:
            intruder_name, ok = QInputDialog.getItem(
                self,
                "Select Intruder",
                "Select intruder for exit:",
                available,
                0,
                False,
            )
        else:
            intruder_name, ok = QInputDialog.getText(
                self, "Intruder Name", "Enter intruder name for exit:"
            )
        if ok and intruder_name:
            if (
                intruder_name in self.annotations
                and "exit" in self.annotations[intruder_name]
            ):
                QMessageBox.warning(
                    self, "Warning", f"Exit already marked for {intruder_name}."
                )
            else:
                if intruder_name not in self.annotations:
                    self.annotations[intruder_name] = {}
                self.annotations[intruder_name]["exit"] = frame
                QMessageBox.information(
                    self,
                    "Annotation",
                    f"Marked exit for {intruder_name} at frame {frame}.",
                )
                self.refresh_annotation_table()

    def closeEvent(self, event):
        if self.cap_preview.isOpened():
            self.cap_preview.release()
        event.accept()

    def toggle_full_screen(self):
        if self.windowState() & Qt.WindowState.WindowFullScreen:
            self.setWindowState(Qt.WindowState.WindowNoState)
        else:
            self.setWindowState(Qt.WindowState.WindowFullScreen)
