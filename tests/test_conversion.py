from pathlib import Path

from PIL import Image


def test_video_to_avi_success(monkeypatch, tmp_path):
    """Simulate a successful ffmpeg run via QProcess and an existing output AVI."""
    from mouse_trap import conversion as conv

    # Fake QProcess that "succeeds"
    class _BA:
        def data(self):
            return b""

    class FakeQProcess:
        def start(self, *_):
            pass

        def waitForFinished(self, *_):
            pass

        def exitCode(self):
            return 0

        def readAllStandardError(self):
            return _BA()

    monkeypatch.setattr(conv, "QProcess", FakeQProcess)

    avi = tmp_path / "out.avi"
    avi.write_bytes(b"\x00" * 2000)  # ensure size > 1000
    ok, msg = conv.video_to_avi("in.mp4", avi)
    assert ok, msg
    assert "Converted" in msg


def test_video_to_avi_failure(monkeypatch, tmp_path):
    """Simulate a failed ffmpeg run via QProcess."""
    from mouse_trap import conversion as conv

    class _BA:
        def data(self):
            return b"boom"

    class FakeQProcess:
        def start(self, *_):
            pass

        def waitForFinished(self, *_):
            pass

        def exitCode(self):
            return 1

        def readAllStandardError(self):
            return _BA()

    monkeypatch.setattr(conv, "QProcess", FakeQProcess)
    ok, msg = conv.video_to_avi("in.mp4", tmp_path / "out.avi")
    assert not ok
    assert "FFmpeg error" in msg


def test_ffmpeg_video_convert_emits_progress(monkeypatch, tmp_path):
    """Ensure -progress output is parsed and progress_signal is emitted."""
    from mouse_trap import conversion as conv

    # Fake QByteArray-like
    class _BA:
        def data(self):
            return b"out_time_ms=1000\n"

    # Fake signal container with connect()
    class _Signal:
        def __init__(self):
            self._cb = None

        def connect(self, cb):
            self._cb = cb

        def emit(self):
            if self._cb:
                self._cb()

    class FakeQProcess:
        class ExitStatus:
            NormalExit = 0

        def __init__(self):
            self.readyReadStandardOutput = _Signal()

        def setProgram(self, *_):
            pass

        def setArguments(self, *_):
            pass

        def start(self):
            # When started, pretend ffmpeg produced a progress line.
            self.readyReadStandardOutput.emit()

        def readAllStandardOutput(self):
            return _BA()

        def waitForFinished(self, *_):
            pass

        def exitStatus(self):
            return FakeQProcess.ExitStatus.NormalExit

        def exitCode(self):
            return 0

    monkeypatch.setattr(conv, "QProcess", FakeQProcess)

    t = conv.ConversionThread(
        input_file=tmp_path / "in.mp4",
        output_file=tmp_path / "out.mkv",
        conversion_type="video_to_video",
    )
    t.total_duration_ms = 2000  # so out_time_ms=1000 -> 50%

    seen = []

    def _on_progress(p):
        seen.append(p)

    t.progress_signal.connect(_on_progress)
    ok, msg = t.ffmpeg_video_convert()
    assert ok, msg
    assert any(p >= 50 for p in seen)


def test_image_to_image_roundtrip(tmp_path):
    """Verify image_to_image path writes an output image."""
    from mouse_trap.conversion import ConversionThread

    src = tmp_path / "in.jpg"
    img = Image.new("RGB", (4, 4), (255, 0, 0))
    img.save(src)

    out = tmp_path / "out.png"
    t = ConversionThread(src, out, "image_to_image")

    result = {}

    def _on_finish(success, msg):
        result["ok"] = success
        result["msg"] = msg

    t.finished_signal.connect(_on_finish)
    t.run()
    assert result["ok"], result["msg"]
    assert out.exists()


def test_pdf_to_image_uses_convert_from_path(monkeypatch, tmp_path):
    """Mock pdf2image to ensure multiple pages are saved with suffixes."""
    from mouse_trap import conversion as conv

    saved = []

    class FakeImage:
        mode = "RGB"

        def convert(self, *_):
            return self

        def save(self, p):
            saved.append(Path(p))

    def fake_convert_from_path(_):
        return [FakeImage(), FakeImage()]  # 2 pages

    monkeypatch.setattr(conv, "convert_from_path", fake_convert_from_path)

    t = conv.ConversionThread(
        input_file=tmp_path / "doc.pdf",
        output_file=tmp_path / "export.png",
        conversion_type="pdf_to_image",
    )
    ok, msg = t.pdf_to_image()
    assert ok, msg
    assert any(p.name.endswith("_page0.png") for p in saved)
    assert any(p.name.endswith("_page1.png") for p in saved)


def test_pandoc_and_docx2pdf_paths(monkeypatch, tmp_path):
    """Mock pypandoc/docx2pdf so tests don't need those tools installed."""
    from mouse_trap import conversion as conv

    # pypandoc: return empty string on success
    monkeypatch.setattr(conv.pypandoc, "convert_file", lambda *a, **k: "")

    # docx2pdf: just create target file
    def _docx2pdf(src, dst):
        Path(dst).write_bytes(b"PDF")

    monkeypatch.setattr(conv, "docx2pdf_convert", _docx2pdf)

    # PDF -> DOCX
    ok, _ = conv.ConversionThread(
        tmp_path / "a.pdf", tmp_path / "a.docx", "pdf_to_docx"
    ).pdf_to_docx()
    assert ok

    # PDF -> TXT
    ok, _ = conv.ConversionThread(
        tmp_path / "a.pdf", tmp_path / "a.txt", "pdf_to_txt"
    ).pdf_to_txt()
    assert ok

    # DOCX -> PDF
    ok, _ = conv.ConversionThread(
        tmp_path / "a.docx", tmp_path / "a.pdf", "docx_to_pdf"
    ).docx_to_pdf()
    assert ok
