# tests/test_gui.py
from pathlib import Path

import pytest

from mouse_trap.gui import MainWindow


def test_update_output_options_respects_mapping(qapp):
    w = MainWindow()
    # Pick a representative type
    w.current_extension = ".pdf"
    w.update_output_options()
    items = [w.output_combo.itemText(i) for i in range(w.output_combo.count())]
    assert items == w.OUTPUT_FORMATS[".pdf"]


@pytest.mark.parametrize(
    "inp,out,expected",
    [
        (".seq", ".mp4", "seq_to_mp4"),
        (".seq", ".avi", "seq_to_avi"),
        (".mp4", ".avi", "video_to_avi"),
        (".mp4", ".gif", "video_to_video"),
        (".jpg", ".png", "image_to_image"),
        (".jpg", ".pdf", "image_to_pdf"),
        (".pdf", ".png", "pdf_to_image"),
        (".pdf", ".docx", "pdf_to_docx"),
        (".pdf", ".txt", "pdf_to_txt"),
        (".docx", ".pdf", "docx_to_pdf"),
        (".docx", ".txt", "docx_to_txt"),
        (".txt", ".pdf", "txt_to_pdf"),
        (".txt", ".docx", "txt_to_docx"),
    ],
)
def test_determine_conversion_type(qapp, inp, out, expected):
    w = MainWindow()
    assert w.determine_conversion_type(inp, out) == expected


def test_clip_by_annotations_validation_errors(qapp, tmp_path):
    w = MainWindow()
    # Output is used only for naming; pick an .mp4 to choose codec map path
    w.output_file = tmp_path / "result.mp4"

    # Missing exit
    ok, msg = w.clip_by_annotations({"A": {"enter": 10}}, Path("dummy.avi"))
    assert not ok and "Incomplete annotation" in msg

    # Exit before enter
    ok, msg = w.clip_by_annotations({"A": {"enter": 10, "exit": 5}}, Path("dummy.avi"))
    assert not ok and "Exit frame occurs before enter frame" in msg

    # Overlapping intervals
    ok, msg = w.clip_by_annotations(
        {"A": {"enter": 10, "exit": 50}, "B": {"enter": 40, "exit": 60}},
        Path("dummy.avi"),
    )
    assert not ok and "Overlapping intruder intervals" in msg
