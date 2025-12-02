import os

from mouse_trap import sleap_cli as sc


def test_canon_path_normalizes():
    p = "C:/Some/Path/../File.mp4"
    norm = sc._canon_path(p)
    # Should be absolute, normalized case/sep for platform
    assert "file.mp4".lower() in norm


def test_parse_latest_status_picks_latest(tmp_path):
    log = tmp_path / "batch.log"
    lines = [
        "2025-10-01T10:00:00\tOK  \tC:/video1.mp4\tC:/out1.slp\n",
        "2025-10-01T10:01:00\tFAIL\tC:/video1.mp4\t1\n",
    ]
    log.write_text("".join(lines), encoding="utf-8")
    latest = sc.parse_latest_status(str(log))
    # Fail should win as the latest line
    key = sc._canon_path("C:/video1.mp4")
    assert latest.get(key) == "FAIL"


def test_args_from_cli_state_minimal():
    spec = [
        {
            "group": "Essential",
            "key": "device",
            "flag": "--device",
            "type": "text",
            "default": "auto",
        },
        {
            "group": "Essential",
            "key": "tracking",
            "flag": "--tracking",
            "type": "bool",
            "default": False,
        },
        {
            "group": "Image",
            "key": "max_height",
            "flag": "--max_height",
            "type": "int_or_none",
            "min": 0,
            "max": 9999,
        },
        {
            "group": "Model",
            "key": "model_paths",
            "flag": "--model_paths",
            "type": "paths",
        },
    ]
    # Build a small state like extract_cli_state() would return
    state = {
        "device": "cuda:0",
        "tracking": True,
        "max_height": 512,
        "model_paths": ["m1", "m2"],
    }
    args = sc.args_from_cli_state(
        state, spec, data_path="in.mp4", output_path="out.slp"
    )
    # Required data/output flags first
    assert args[:4] == ["--data_path", "in.mp4", "--output_path", "out.slp"]
    # Tracking included as a flag, device and max_height with values, two model_paths entries
    joined = " ".join(args)
    assert "--tracking" in joined
    assert "--device cuda:0" in joined
    assert "--max_height 512" in joined
    assert joined.count("--model_paths") == 2


def test_build_tabs_and_extract_state(qapp):
    # Use a tiny spec to keep the UI light
    spec = [
        {
            "group": "Essential",
            "key": "device",
            "flag": "--device",
            "type": "text",
            "default": "auto",
        },
        {
            "group": "Essential",
            "key": "batch_size",
            "flag": "--batch_size",
            "type": "int",
            "min": 1,
            "max": 128,
            "default": 4,
        },
        {
            "group": "Image",
            "key": "ensure_rgb",
            "flag": "--ensure_rgb",
            "type": "bool",
            "default": False,
        },
        {
            "group": "Image",
            "key": "integral_refinement",
            "flag": "--integral_refinement",
            "type": "choice",
            "choices": ["integral", "none"],
            "default": "integral",
        },
    ]
    tabs, controls = sc.build_cli_tabs(None, spec)
    assert tabs.count() == 2  # Essential, Image groups present
    # Modify some values
    controls["device"].setText("cpu")
    controls["batch_size"].setValue(8)
    controls["ensure_rgb"].setChecked(True)
    controls["integral_refinement"].setCurrentText("none")

    state = sc.extract_cli_state(controls, spec)
    assert state == {
        "device": "cpu",
        "batch_size": 8,
        "ensure_rgb": True,
        "integral_refinement": "none",
    }


def test_collect_videos_skips_frames_dirs(tmp_path):
    root = tmp_path / "root"
    (root / "_frames").mkdir(parents=True)
    (root / "sub").mkdir()
    (root / "_frames" / "bad.mp4").write_text("x")
    (root / "a.mp4").write_text("x")
    (root / "sub" / "b.mp4").write_text("x")

    params = dict(
        videos_root=str(root),
        outdir=str(root / "pred"),
        log=str(root / "log.txt"),
        respect_log=False,
        include_subfolders=True,
        env="sleap",
        exts={".mp4", ".avi"},
        conda_exe="conda",
        cli_state={},
    )
    t = sc.SleapBatchThread(params)
    vids = t._collect_videos()
    joined = " ".join(vids)
    assert "bad.mp4" not in joined  # skipped
    assert "a.mp4" in joined and "b.mp4" in joined


def test_build_out_path_sanitizes(tmp_path):
    params = dict(
        videos_root=str(tmp_path / "root"),
        outdir=str(tmp_path / "pred"),
        log=str(tmp_path / "log.txt"),
        respect_log=False,
        include_subfolders=False,
        env="sleap",
        exts={".mp4"},
        conda_exe="conda",
        cli_state={},
    )
    t = sc.SleapBatchThread(params)
    v = str(tmp_path / "root" / "dir:with*bad?chars" / "x.mp4")
    out = t._build_out_path(v)
    assert out.endswith(".predictions.slp")
    rel = os.path.relpath(out, params["outdir"])
    assert all(c not in rel for c in ':*?"<>|')
