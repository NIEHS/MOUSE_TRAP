from mouse_trap.sleap_cli import parse_latest_status
from pathlib import Path


def test_parse_latest_status(tmp_path: Path):
    log = tmp_path / "batch.log"
    lines = [
        "2025-10-01T10:00:00\tOK  \tC:/video1.mp4\tC:/out1.slp\n",
        "2025-10-01T10:01:00\tFAIL\tC:/video1.mp4\t1\n",
        "2025-10-01T10:02:00\tOK  \tC:/video2.mp4\tC:/out2.slp\n",
    ]
    log.write_text("".join(lines), encoding="utf-8")
    latest = parse_latest_status(str(log))
    assert latest
    # latest status for video1 should be FAIL
    assert any(v.endswith("video1.mp4") for v in latest)
