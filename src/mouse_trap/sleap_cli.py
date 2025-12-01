import os
import platform
import re
import shutil
import subprocess
from datetime import datetime

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
    QTabWidget,
    QDoubleSpinBox,
    QSpinBox,
)
from typing import Any, Dict, List, Tuple, Optional


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _canon_path(p: str) -> str:
    try:
        return os.path.normcase(os.path.abspath(os.path.normpath(str(p))))
    except Exception:
        return str(p).replace("/", os.sep).lower()


def parse_latest_status(log_path: str) -> Dict[str, str]:
    latest = {}
    if not os.path.exists(log_path):
        return latest
    with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            parts = raw.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            status = parts[1].strip().upper()
            in_path = parts[2].strip()
            if status in ("OK", "FAIL"):
                latest[_canon_path(in_path)] = status
    return latest


def _resolve_conda_executable() -> str:
    for name in ("conda.exe", "conda.bat", "conda"):
        p = shutil.which(name)
        if p:
            return p

    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, "anaconda3", "condabin", "conda.bat"),
        os.path.join(home, "miniconda3", "condabin", "conda.bat"),
        r"C:\ProgramData\Anaconda3\condabin\conda.bat",
        r"C:\ProgramData\Miniconda3\condabin\conda.bat",
        r"C:\Users\harperrm\anaconda3\condabin\conda.bat",
        r"C:\Users\harperrm\miniconda3\condabin\conda.bat",
    ]
    for c in candidates:
        c = os.path.expandvars(c)
        if os.path.exists(c):
            return c
    return "conda"


# -----------------------------------------------------------------------------
# Full sleap-nn "track" CLI spec
# -----------------------------------------------------------------------------
CLI_SPEC = [
    {
        "group": "Essential",
        "key": "data_path",
        "flag": "--data_path",
        "short": "-i",
        "type": "path_in",
        "required": True,
        "help": "Video (.mp4, etc.) or .slp",
    },
    {
        "group": "Essential",
        "key": "model_paths",
        "flag": "--model_paths",
        "short": "-m",
        "type": "paths",
        "required": False,
        "help": "One or more model directories",
    },
    {
        "group": "Essential",
        "key": "output_path",
        "flag": "--output_path",
        "short": "-o",
        "type": "path_out",
        "help": "Output .slp (defaults to <input>.predictions.slp)",
    },
    {
        "group": "Essential",
        "key": "device",
        "flag": "--device",
        "short": "-d",
        "type": "text",
        "placeholder": "auto | cpu | cuda:0",
        "default": "auto",
    },
    {
        "group": "Essential",
        "key": "batch_size",
        "flag": "--batch_size",
        "short": "-b",
        "type": "int",
        "min": 1,
        "max": 2048,
        "default": 4,
    },
    {
        "group": "Essential",
        "key": "max_instances",
        "flag": "--max_instances",
        "short": "-n",
        "type": "int_or_none",
        "min": 0,
        "max": 999,
        "default": None,
    },
    {
        "group": "Essential",
        "key": "tracking",
        "flag": "--tracking",
        "short": "-t",
        "type": "bool",
        "default": False,
    },
    {
        "group": "Essential",
        "key": "peak_threshold",
        "flag": "--peak_threshold",
        "type": "float",
        "min": 0.0,
        "max": 1.0,
        "default": 0.2,
    },
    {
        "group": "Essential",
        "key": "integral_refinement",
        "flag": "--integral_refinement",
        "type": "choice",
        "choices": ["integral", "none"],
        "default": "integral",
    },
    {
        "group": "Model",
        "key": "backbone_ckpt_path",
        "flag": "--backbone_ckpt_path",
        "type": "path_in",
    },
    {
        "group": "Model",
        "key": "head_ckpt_path",
        "flag": "--head_ckpt_path",
        "type": "path_in",
    },
    {
        "group": "Image",
        "key": "max_height",
        "flag": "--max_height",
        "type": "int_or_none",
        "min": 0,
        "max": 16384,
    },
    {
        "group": "Image",
        "key": "max_width",
        "flag": "--max_width",
        "type": "int_or_none",
        "min": 0,
        "max": 16384,
    },
    {
        "group": "Image",
        "key": "input_scale",
        "flag": "--input_scale",
        "type": "float_or_none",
        "min": 0.01,
        "max": 100.0,
    },
    {"group": "Image", "key": "ensure_rgb", "flag": "--ensure_rgb", "type": "bool"},
    {
        "group": "Image",
        "key": "ensure_grayscale",
        "flag": "--ensure_grayscale",
        "type": "bool",
    },
    {
        "group": "Image",
        "key": "crop_size",
        "flag": "--crop_size",
        "type": "int_or_none",
        "min": 0,
        "max": 4096,
    },
    {"group": "Image", "key": "anchor_part", "flag": "--anchor_part", "type": "text"},
    {
        "group": "Data",
        "key": "only_labeled_frames",
        "flag": "--only_labeled_frames",
        "type": "bool",
    },
    {
        "group": "Data",
        "key": "only_suggested_frames",
        "flag": "--only_suggested_frames",
        "type": "bool",
    },
    {
        "group": "Data",
        "key": "video_index",
        "flag": "--video_index",
        "type": "int_or_none",
        "min": 0,
        "max": 9999,
    },
    {
        "group": "Data",
        "key": "video_dataset",
        "flag": "--video_dataset",
        "type": "text",
    },
    {
        "group": "Data",
        "key": "video_input_format",
        "flag": "--video_input_format",
        "type": "choice",
        "choices": ["channels_last", "channels_first"],
        "default": "channels_last",
    },
    {
        "group": "Data",
        "key": "frames",
        "flag": "--frames",
        "type": "text",
        "placeholder": "e.g. 0-100,200-300",
    },
    {
        "group": "Data",
        "key": "no_empty_frames",
        "flag": "--no_empty_frames",
        "type": "bool",
    },
    {
        "group": "Performance",
        "key": "queue_maxsize",
        "flag": "--queue_maxsize",
        "type": "int",
        "min": 1,
        "max": 4096,
        "default": 8,
    },
    {
        "group": "Tracking",
        "key": "tracking_window_size",
        "flag": "--tracking_window_size",
        "type": "int",
        "min": 1,
        "max": 999,
        "default": 5,
    },
    {
        "group": "Tracking",
        "key": "candidates_method",
        "flag": "--candidates_method",
        "type": "choice",
        "choices": ["fixed_window", "local_queues"],
        "default": "fixed_window",
    },
    {
        "group": "Tracking",
        "key": "min_new_track_points",
        "flag": "--min_new_track_points",
        "type": "int",
        "min": 0,
        "max": 1000,
        "default": 0,
    },
    {
        "group": "Tracking",
        "key": "min_match_points",
        "flag": "--min_match_points",
        "type": "int",
        "min": 0,
        "max": 1000,
        "default": 0,
    },
    {
        "group": "Tracking",
        "key": "features",
        "flag": "--features",
        "type": "choice",
        "choices": ["keypoints", "centroids", "bboxes", "image"],
        "default": "keypoints",
    },
    {
        "group": "Tracking",
        "key": "scoring_method",
        "flag": "--scoring_method",
        "type": "choice",
        "choices": ["oks", "cosine_sim", "iou", "euclidean_dist"],
        "default": "oks",
    },
    {
        "group": "Tracking",
        "key": "scoring_reduction",
        "flag": "--scoring_reduction",
        "type": "choice",
        "choices": ["mean", "max", "robust_quantile"],
        "default": "mean",
    },
    {
        "group": "Tracking",
        "key": "robust_best_instance",
        "flag": "--robust_best_instance",
        "type": "float",
        "min": 0.0,
        "max": 1.0,
        "default": 1.0,
    },
    {
        "group": "Tracking",
        "key": "track_matching_method",
        "flag": "--track_matching_method",
        "type": "choice",
        "choices": ["hungarian", "greedy"],
        "default": "hungarian",
    },
    {
        "group": "Tracking",
        "key": "max_tracks",
        "flag": "--max_tracks",
        "type": "int_or_none",
        "min": 0,
        "max": 999,
        "default": None,
    },
    {"group": "Tracking", "key": "use_flow", "flag": "--use_flow", "type": "bool"},
    {
        "group": "Tracking",
        "key": "of_img_scale",
        "flag": "--of_img_scale",
        "type": "float",
        "min": 0.01,
        "max": 10.0,
        "default": 1.0,
        "enable_if": {"use_flow": True},
    },
    {
        "group": "Tracking",
        "key": "of_window_size",
        "flag": "--of_window_size",
        "type": "int",
        "min": 3,
        "max": 101,
        "default": 21,
        "enable_if": {"use_flow": True},
    },
    {
        "group": "Tracking",
        "key": "of_max_levels",
        "flag": "--of_max_levels",
        "type": "int",
        "min": 1,
        "max": 8,
        "default": 3,
        "enable_if": {"use_flow": True},
    },
    {
        "group": "Tracking",
        "key": "post_connect_single_breaks",
        "flag": "--post_connect_single_breaks",
        "type": "bool",
    },
    {
        "group": "Tracking (legacy-compatible)",
        "key": "tracking_pre_cull_to_target",
        "flag": "--tracking_pre_cull_to_target",
        "type": "bool",
    },
    {
        "group": "Tracking (legacy-compatible)",
        "key": "tracking_target_instance_count",
        "flag": "--tracking_target_instance_count",
        "type": "int_or_none",
        "min": 0,
        "max": 64,
    },
    {
        "group": "Tracking (legacy-compatible)",
        "key": "tracking_pre_cull_iou_threshold",
        "flag": "--tracking_pre_cull_iou_threshold",
        "type": "float",
        "min": 0.0,
        "max": 1.0,
    },
    {
        "group": "Tracking (legacy-compatible)",
        "key": "tracking_clean_instance_count",
        "flag": "--tracking_clean_instance_count",
        "type": "int_or_none",
        "min": 0,
        "max": 64,
    },
    {
        "group": "Tracking (legacy-compatible)",
        "key": "tracking_clean_iou_threshold",
        "flag": "--tracking_clean_iou_threshold",
        "type": "float",
        "min": 0.0,
        "max": 1.0,
    },
]

# -------- GUI builders for CLI_SPEC (PyQt6) --------


def _make_widget(spec: Dict[str, Any]) -> Tuple[QWidget, QWidget]:
    t = spec["type"]
    if t in ("path_in", "path_out", "paths", "text"):
        w = QLineEdit()
        if spec.get("placeholder"):
            w.setPlaceholderText(spec["placeholder"])
        if t == "text" and spec.get("default") not in (None, ""):
            w.setText(str(spec["default"]))
        if t.startswith("path"):
            btn = QPushButton("Browse…")
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.addWidget(w, 1)
            h.addWidget(btn, 0)

            def browse():
                if t == "path_out":
                    p, _ = QFileDialog.getSaveFileName(row, "Select file")
                elif t == "paths":
                    p = QFileDialog.getExistingDirectory(row, "Select model dir") or ""
                else:
                    p, _ = QFileDialog.getOpenFileName(row, "Select file")
                if p:
                    if t == "paths" and w.text():
                        w.setText(w.text() + ";" + p)
                    else:
                        w.setText(p)

            btn.clicked.connect(browse)
            return row, w
        return w, w
    if t in ("int", "int_or_none"):
        w = QSpinBox()
        w.setRange(spec.get("min", 0), spec.get("max", 10**6))
        if spec.get("default") is not None:
            w.setValue(int(spec["default"]))
        return w, w
    if t in ("float", "float_or_none"):
        w = QDoubleSpinBox()
        w.setDecimals(4)
        w.setRange(spec.get("min", -1e9), spec.get("max", 1e9))
        if spec.get("default") is not None:
            w.setValue(float(spec["default"]))
        return w, w
    if t == "bool":
        w = QCheckBox()
        if spec.get("default"):
            w.setChecked(True)
        return w, w
    if t == "choice":
        w = QComboBox()
        [w.addItem(c) for c in spec["choices"]]
        if spec.get("default"):
            w.setCurrentText(spec["default"])
        return w, w
    raise ValueError(f"Unknown type {t}")


def build_cli_tabs(
    parent: QWidget, spec_list: List[Dict[str, Any]]
) -> Tuple[QTabWidget, Dict[str, QWidget]]:
    tabs = QTabWidget(parent)
    controls = {}
    groups = {}
    for s in spec_list:
        groups.setdefault(s["group"], []).append(s)

    for gname, items in groups.items():
        page = QWidget()
        form = QFormLayout(page)
        for s in items:
            wrow, wcore = _make_widget(s)
            label = s["flag"]
            if s.get("short"):
                label = f"{s['flag']} ({s['short']})"
            if s.get("help"):
                wcore.setToolTip(s["help"])
            form.addRow(label, wrow)
            controls[s["key"]] = wcore
        tabs.addTab(page, gname)

    def _apply_enables():
        def _val(ctrl):
            from PyQt6.QtWidgets import (
                QCheckBox,
                QComboBox,
                QSpinBox,
                QDoubleSpinBox,
            )

            if isinstance(ctrl, QCheckBox):
                return ctrl.isChecked()
            if isinstance(ctrl, QComboBox):
                return ctrl.currentText()
            if isinstance(ctrl, (QSpinBox, QDoubleSpinBox)):
                return ctrl.value()
            return ctrl.text().strip()

        values = {k: _val(c) for k, c in controls.items()}
        for s in spec_list:
            if "enable_if" in s:
                ok = True
                for depk, depv in s["enable_if"].items():
                    cur = values.get(depk)
                    if isinstance(cur, str) and isinstance(depv, bool):
                        cur = cur.lower() in ("1", "true", "yes", "on")
                    ok = ok and (cur == depv)
                controls[s["key"]].setEnabled(ok)

    from PyQt6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QLineEdit,
        QSpinBox,
        QDoubleSpinBox,
    )

    for w in controls.values():
        if isinstance(w, QCheckBox):
            w.stateChanged.connect(_apply_enables)
        elif isinstance(w, QComboBox):
            w.currentIndexChanged.connect(_apply_enables)
        elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
            w.valueChanged.connect(_apply_enables)
        elif isinstance(w, QLineEdit):
            w.textChanged.connect(_apply_enables)
    _apply_enables()
    return tabs, controls


def extract_cli_state(
    controls: Dict[str, QWidget], spec_list: List[Dict[str, Any]]
) -> Dict[str, Any]:
    state = {}
    from PyQt6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QSpinBox,
        QDoubleSpinBox,
    )

    for s in spec_list:
        w = controls[s["key"]]
        if isinstance(w, QCheckBox):
            state[s["key"]] = bool(w.isChecked())
        elif isinstance(w, QComboBox):
            state[s["key"]] = w.currentText()
        elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
            state[s["key"]] = w.value()
        else:
            txt = w.text().strip()
            if s["type"] == "paths":
                val = [p.strip() for p in txt.split(";") if p.strip()]
            else:
                val = txt
            state[s["key"]] = val
    return state


def args_from_cli_state(
    state: Dict[str, Any],
    spec_list: List[Dict[str, Any]],
    data_path: str,
    output_path: str,
    model_default: str = "",
) -> List[str]:
    args = []
    for s in spec_list:
        key = s["key"]
        flag = s["flag"]
        t = s["type"]
        if key in ("data_path", "output_path"):
            continue
        val = state.get(key, None)
        if t == "bool":
            if val:
                args.append(flag)
            continue
        if t == "paths":
            if val:
                for p in val:
                    args += [flag, str(p)]
            continue
        if val in (None, "", [], 0) and t not in (
            "int",
            "float",
            "choice",
            "int_or_none",
            "float_or_none",
        ):
            continue
        if t in ("int_or_none", "float_or_none"):
            if val in (None, "", "None"):
                continue
        if t == "text" and not val:
            continue
        args += [flag, str(val)]
    args = ["--data_path", str(data_path), "--output_path", str(output_path)] + args
    has_m = any(a in ("--model_paths", "-m") for a in args)
    if not has_m and model_default:
        args = ["--model_paths", str(model_default)] + args
    return args


class SleapBatchDialog(QDialog):
    def __init__(self, parent: Optional[object] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Run SLEAP Inference")
        form = QFormLayout(self)

        def browse(edit: QLineEdit, is_dir=True):
            if is_dir:
                p = QFileDialog.getExistingDirectory(
                    self, "Select Folder", edit.text() or os.path.expanduser("~")
                )
            else:
                p, _ = QFileDialog.getOpenFileName(
                    self, "Select File", edit.text() or os.path.expanduser("~")
                )
            if p:
                edit.setText(p)

        self.videosRoot = QLineEdit(r"C:\Users\harperrm\GPU Run\clip (use for SLEAP)")
        self.outDir = QLineEdit(
            r"C:\Users\harperrm\GPU Run\SLEAP_v4 (updated)\predictions"
        )
        self.logPath = QLineEdit(
            r"C:\Users\harperrm\GPU Run\SLEAP_v4 (updated)\predictions\batch_infer.log"
        )

        for label, edit, is_dir in [
            ("Videos folder", self.videosRoot, True),
            ("Predictions folder", self.outDir, True),
            ("Log file", self.logPath, False),
        ]:
            row = QWidget(self)
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.addWidget(edit, 1)
            b = QPushButton("Browse…", self)
            b.clicked.connect(lambda _, e=edit, d=is_dir: browse(e, d))
            h.addWidget(b, 0)
            if label == "Videos folder":
                self.includeSubdirs = QCheckBox(" Include subfolders", self)
                self.includeSubdirs.setChecked(False)
                h.addWidget(self.includeSubdirs, 0)
            form.addRow(label, row)
        self.respectLog = QCheckBox(" Skip items with latest status = OK")
        self.respectLog.setChecked(True)
        form.addRow(self.respectLog)

        self.cliTabs, self.cliControls = build_cli_tabs(self, CLI_SPEC)
        form.addRow(self.cliTabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> Dict[str, Any]:
        cli_state = extract_cli_state(self.cliControls, CLI_SPEC)
        return dict(
            videos_root=self.videosRoot.text().strip(),
            outdir=self.outDir.text().strip(),
            log=self.logPath.text().strip(),
            respect_log=self.respectLog.isChecked(),
            include_subfolders=self.includeSubdirs.isChecked(),
            env="sleap",
            exts={".mp4", ".avi", ".mov", ".mkv", ".h5"},
            conda_exe=_resolve_conda_executable(),
            cli_state=cli_state,
        )


class SleapBatchThread(QThread):
    """Run a SLEAP batch process in a worker thread."""

    #: Progress updates as (percent, video_basename).
    progress = pyqtSignal(int, str)

    #: One line of textual output from the SLEAP CLI process.
    line = pyqtSignal(str)

    #: Emitted once when all batch jobs have completed.
    done = pyqtSignal()

    def __init__(self, params: Dict[str, Any], parent: Optional[object] = None) -> None:
        super().__init__(parent)
        self.p = params

    def _collect_videos(self) -> List[str]:
        vids = []
        root = self.p["videos_root"]
        if self.p.get("include_subfolders", False):
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [
                    d for d in dirnames if d != "_frames" and not d.endswith("_frames")
                ]
                for fn in filenames:
                    ext = os.path.splitext(fn)[1].lower()
                    if ext in self.p["exts"]:
                        full = os.path.join(dirpath, fn)
                        if re.search(r"(?i)[/\\]_frames([/\\]|$)", full):
                            continue
                        vids.append(full)
        else:
            try:
                for fn in os.listdir(root):
                    full = os.path.join(root, fn)
                    if not os.path.isfile(full):
                        continue
                    ext = os.path.splitext(fn)[1].lower()
                    if ext in self.p["exts"]:
                        if re.search(r"(?i)[/\\]_frames([/\\]|$)", full):
                            continue
                        vids.append(full)
            except FileNotFoundError:
                pass
        return vids

    def _build_out_path(self, video_path: str) -> str:
        rel = os.path.relpath(video_path, self.p["videos_root"])
        safe = re.sub(r'[\\/:*?"<>|]', "_", rel)
        return os.path.join(self.p["outdir"], f"{safe}.predictions.slp")

    def _sleap_args(self, v: str, out_path: str) -> List[str]:
        sleap_nn = os.environ.get("SLEAP_NN", "")
        if sleap_nn and os.path.exists(sleap_nn):
            base = [sleap_nn, "track"]
        else:
            found_nn_track = shutil.which("sleap-nn-track")
            found_nn = shutil.which("sleap-nn")
            if found_nn_track:
                base = [found_nn_track]
            elif found_nn:
                base = [found_nn, "track"]
            else:
                conda_exe = self.p["conda_exe"]
                envname = self.p["env"]
                if platform.system() == "Windows":
                    conda_cmd = f'"{conda_exe}"' if " " in conda_exe else conda_exe
                    base = [
                        "cmd.exe",
                        "/d",
                        "/c",
                        conda_cmd,
                        "run",
                        "--no-capture-output",
                        "-n",
                        envname,
                        "sleap-nn",
                        "track",
                    ]
                else:
                    base = [
                        conda_exe,
                        "run",
                        "--no-capture-output",
                        "-n",
                        envname,
                        "sleap-nn",
                        "track",
                    ]

        state = self.p.get("cli_state", {}) or {}
        cli_args = args_from_cli_state(
            state, CLI_SPEC, data_path=v, output_path=out_path
        )
        return base + cli_args

    def run(self) -> None:
        try:
            os.makedirs(self.p["outdir"], exist_ok=True)
            latest = parse_latest_status(self.p["log"]) if self.p["respect_log"] else {}
            videos = self._collect_videos()

            total = len(videos)
            done = 0
            for v in videos:
                if self.p["respect_log"] and latest.get(_canon_path(v)) == "OK":
                    self.line.emit(f"Skip (OK in log): {v}")
                    done += 1
                    pct = int(done * 100 / max(1, total))
                    self.progress.emit(pct, os.path.basename(v))
                    continue

                out_path = self._build_out_path(v)
                args = self._sleap_args(v, out_path)

                self.line.emit(f"Running sleap-nn track: {v}")
                env = dict(os.environ)
                env.setdefault("PYTHONUNBUFFERED", "1")
                env.setdefault("PYTHONIOENCODING", "utf-8")
                env.setdefault("TERM", "xterm")
                env.setdefault("RICH_FORCE_TERMINAL", "1")
                env.setdefault("FORCE_COLOR", "1")
                try:
                    self.line.emit("CMD: " + " ".join(args))
                except Exception:
                    pass

                proc = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    env=env,
                )
                buf = ""
                if proc.stdout:
                    while True:
                        ch = proc.stdout.read(1)
                        if not ch:
                            break
                        buf += ch
                        if ch == "\r" or ch == "\n":
                            line = buf.rstrip("\r\n")
                            if line:
                                self.line.emit(line)
                            buf = ""
                if buf.strip():
                    self.line.emit(buf.strip())
                proc.wait()
                rc = proc.returncode

                ts = datetime.now().isoformat(timespec="seconds")
                in_key = _canon_path(v)
                with open(self.p["log"], "a", encoding="utf-8") as f:
                    if rc == 0 and os.path.exists(out_path):
                        f.write(f"{ts}\tOK  \t{in_key}\t{out_path}\n")
                    else:
                        f.write(f"{ts}\tFAIL\t{in_key}\t{rc}\n")

                done += 1
                pct = int(done * 100 / max(1, total))
                self.progress.emit(pct, os.path.basename(v))
        finally:
            self.done.emit()
