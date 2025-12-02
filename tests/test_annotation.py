from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QTableWidget

from mouse_trap.annotation import VideoAnnotationDialog


def _minimal_dialog(qapp):
    """
    Build a 'bare' VideoAnnotationDialog-like object without running the heavy __init__.
    We set only the attributes used by the methods under test.
    """
    dlg = VideoAnnotationDialog.__new__(VideoAnnotationDialog)
    dlg.annotations = {}
    # Minimal table the dialog expects
    dlg.annotationTable = QTableWidget()
    dlg.annotationTable.setColumnCount(3)
    dlg.annotationTable.setHorizontalHeaderLabels(["Intruder", "Enter", "Exit"])
    return dlg


def test_refresh_annotation_table_populates_rows(qapp):
    dlg = _minimal_dialog(qapp)
    dlg.annotations = {
        "Alice": {"enter": 10, "exit": 20},
        "Bob": {"enter": 5, "exit": 9},
    }
    VideoAnnotationDialog.refresh_annotation_table(dlg)
    assert dlg.annotationTable.rowCount() == 2
    # "Intruder" cell should be non-editable
    flags = dlg.annotationTable.item(0, 0).flags()
    assert not (flags & Qt.ItemFlag.ItemIsEditable)


def test_table_item_changed_updates_dict(qapp):
    dlg = _minimal_dialog(qapp)
    # Seed with one intruder row
    dlg.annotations = {"Alice": {"enter": 10, "exit": 20}}
    VideoAnnotationDialog.refresh_annotation_table(dlg)

    # Change Alice's enter frame to 12, then call handler
    dlg.annotationTable.item(0, 1).setText("12")
    changed_item = dlg.annotationTable.item(0, 1)
    VideoAnnotationDialog.table_item_changed(dlg, changed_item)
    assert dlg.annotations["Alice"]["enter"] == 12


def test_delete_key_removes_selected_rows(qapp):
    dlg = _minimal_dialog(qapp)
    dlg.annotations = {
        "Alice": {"enter": 10, "exit": 20},
        "Bob": {"enter": 1, "exit": 2},
    }
    VideoAnnotationDialog.refresh_annotation_table(dlg)
    # Select first row and press Delete
    dlg.annotationTable.selectRow(0)
    e = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier
    )
    consumed = VideoAnnotationDialog.eventFilter(dlg, dlg.annotationTable, e)
    assert consumed  # dialog handled the event
    assert "Alice" not in dlg.annotations
    assert "Bob" in dlg.annotations


def test_perform_single_click_seeks_by_frame(qapp):
    dlg = _minimal_dialog(qapp)
    dlg.annotations = {"Alice": {"enter": 10, "exit": 20}}
    VideoAnnotationDialog.refresh_annotation_table(dlg)

    # Stub mediaPlayer with only setPosition()
    class StubPlayer:
        def __init__(self):
            self.last = None

        def setPosition(self, ms):
            self.last = ms

    dlg.mediaPlayer = StubPlayer()
    dlg.fps = 25  # 25 fps -> 40ms/frame
    dlg.total_frames = 100
    # Put frame "11" in Alice's Enter cell and single-click it
    dlg.annotationTable.item(0, 1).setText("11")
    dlg.clicked_row = 0
    dlg.clicked_column = 1
    VideoAnnotationDialog.perform_single_click(dlg)
    assert dlg.mediaPlayer.last == int((11 - 1) * (1000 / 25))
