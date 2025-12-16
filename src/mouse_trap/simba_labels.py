"""Helpers to convert Caltech Behavior Annotator text files into
SimBA-compatible ``targets_inserted`` CSVs.

This module is GUI-agnostic: it exposes pure functions that operate on
paths and optionally report progress via a callback. The GUI can import
:func:`convert_caltech_to_simba_targets` and wire it to buttons or dialogs.

Usage (from code)
-----------------
from mouse_trap.simba_labels import convert_caltech_to_simba_targets

ok, msg = convert_caltech_to_simba_targets(
    annotation_path="myvideo.txt",
    features_csv_path="path/to/features_extracted/myvideo.csv",
    output_csv_path="path/to/targets_inserted/myvideo.csv",
)

The output CSV will contain all original feature columns plus one 0/1
column per behavior, suitable for SimBA's ``targets_inserted`` folder.

The logic assumes that frame numbers in the Caltech file are 1-based and
correspond to rows in the features CSV in order. If you discover an
off-by-one issue for your pipeline you can tweak ``frame_offset``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd


# Behaviors that are *usually* not used as classifier targets
_DEFAULT_EXCLUDED_BEHAVIORS: tuple[str, ...] = ("other",)


@dataclass
class CaltechSegment:
    """One labeled bout from a Caltech Behavior Annotator file."""

    start_frame: int
    end_frame: int
    behavior: str


@dataclass
class CaltechAnnotation:
    """Parsed representation of a Caltech Behavior Annotator file."""

    behavior_code_map: Dict[str, str]
    segments: List[CaltechSegment]


def parse_caltech_annotation(path: Union[str, Path]) -> CaltechAnnotation:
    """Parse a Caltech Behavior Annotator .txt file.

    Parameters
    ----------
    path:
        Path to the annotation text file produced by Caltech Behavior Annotator.

    Returns
    -------
    CaltechAnnotation
        Object containing a mapping ``behavior_name -> single-character code``
        and a list of labeled segments as :class:`CaltechSegment` instances.
    """
    path = Path(path)
    behavior_code_map: Dict[str, str] = {}
    segments: List[CaltechSegment] = []

    with path.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    in_config = False
    in_segments = False

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        if line.startswith("Configuration file"):
            in_config = True
            continue

        # Inside the configuration block until we hit the segment header
        if in_config:
            # Start of segment table line, e.g. "S1: start    end     type"
            if line.startswith("S") and "start" in line and "end" in line:
                in_config = False
                in_segments = True
                continue

            # Behavior line: "<name> <single_char_code>"
            parts = line.split()
            if len(parts) == 2:
                behavior, code = parts
                behavior_code_map[behavior] = code
            continue

        if in_segments:
            # Skip header-like lines and separators
            if line.startswith("S") and ":" in line:
                continue
            if set(line) <= {"-"}:
                continue

            parts = line.split()
            if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
                start = int(parts[0])
                end = int(parts[1])
                behavior = parts[2]
                segments.append(
                    CaltechSegment(
                        start_frame=start,
                        end_frame=end,
                        behavior=behavior,
                    )
                )

    if not segments:
        raise ValueError(f"No behavior segments found in {path}")

    return CaltechAnnotation(behavior_code_map=behavior_code_map, segments=segments)


def _determine_behaviors_to_use(
    annotation: CaltechAnnotation,
    included_behaviors: Optional[Iterable[str]] = None,
    include_all_behaviors_from_annotation: bool = True,
    excluded_behaviors: Sequence[str] = _DEFAULT_EXCLUDED_BEHAVIORS,
) -> List[str]:
    """Resolve which behavior names should produce classifier columns."""
    present = sorted({seg.behavior for seg in annotation.segments})

    if included_behaviors is not None:
        include_set = {b.strip() for b in included_behaviors}
        return [b for b in present if b in include_set]

    if include_all_behaviors_from_annotation:
        excl = set(excluded_behaviors)
        return [b for b in present if b not in excl]

    # Fallback: include nothing if no explicit list and include_all is False
    return []


def build_label_matrix(
    n_frames: int,
    annotation: CaltechAnnotation,
    behaviors: Sequence[str],
    frame_offset: int = 1,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> pd.DataFrame:
    """Create a frame-by-behavior 0/1 label matrix.

    Parameters
    ----------
    n_frames:
        Number of frames / rows in the features CSV.
    annotation:
        Parsed Caltech annotation object.
    behaviors:
        Iterable of behavior names that should become columns.
    frame_offset:
        Offset applied when converting Caltech frame numbers to row indices::

            row_index = frame_number - frame_offset

        With the default ``frame_offset=1``, frame 1 in the annotation maps
        to index 0 in the CSV.
    progress_callback:
        Optional callable that receives an integer percentage (0-100) as
        progress feedback while filling the matrix.

    Returns
    -------
    pandas.DataFrame
        Index ``0 .. n_frames-1``, columns = behavior names, dtype=int8.
    """
    if not behaviors:
        raise ValueError("No behaviors provided to build_label_matrix")

    # Create an empty matrix of zeros
    labels = pd.DataFrame(
        data=0,
        index=np.arange(n_frames, dtype=int),
        columns=list(behaviors),
        dtype=np.int8,
    )

    # Fill segments for each behavior
    total_segments = len(annotation.segments)
    for idx, seg in enumerate(annotation.segments, start=1):
        if seg.behavior not in behaviors:
            continue

        start_idx = seg.start_frame - frame_offset
        end_idx = seg.end_frame - frame_offset

        if start_idx < 0 or end_idx >= n_frames:
            raise ValueError(
                f"Segment {seg.behavior} ({seg.start_frame}-{seg.end_frame}) "
                f"maps to rows {start_idx}-{end_idx}, which is outside "
                f"0..{n_frames-1}. Adjust 'frame_offset' if this is an "
                "off-by-one error, otherwise check your inputs."
            )

        labels.iloc[start_idx : end_idx + 1, labels.columns.get_loc(seg.behavior)] = 1

        if progress_callback is not None and total_segments > 0:
            # Rough progress from filling labels (30-90% of overall work).
            pct = 30 + int(60 * idx / total_segments)
            progress_callback(min(pct, 99))

    return labels


def convert_caltech_to_simba_targets(
    annotation_path: Union[str, Path],
    features_csv_path: Union[str, Path],
    output_csv_path: Union[str, Path],
    included_behaviors: Optional[Iterable[str]] = None,
    include_all_behaviors_from_annotation: bool = True,
    frame_offset: int = 1,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> Tuple[bool, str]:
    """Combine SimBA features with Caltech labels into a ``targets_inserted`` CSV.

    This is the main entry point that the GUI should call.
    """
    annotation_path = Path(annotation_path)
    features_csv_path = Path(features_csv_path)
    output_csv_path = Path(output_csv_path)

    if progress_callback is not None:
        progress_callback(5)

    if not features_csv_path.exists():
        return False, f"Features CSV not found: {features_csv_path}"
    if not annotation_path.exists():
        return False, f"Annotation file not found: {annotation_path}"

    try:
        features_df = pd.read_csv(features_csv_path)
    except Exception as exc:
        return False, f"Failed to read features CSV: {exc}"

    n_frames = len(features_df)
    if n_frames == 0:
        return False, f"Features CSV {features_csv_path} has no rows."

    if progress_callback is not None:
        progress_callback(15)

    try:
        annotation = parse_caltech_annotation(annotation_path)
    except Exception as exc:
        return False, f"Failed to parse Caltech annotation: {exc}"

    unique_behaviors = sorted({seg.behavior for seg in annotation.segments})

    behaviors = _determine_behaviors_to_use(
        annotation=annotation,
        included_behaviors=included_behaviors,
        include_all_behaviors_from_annotation=include_all_behaviors_from_annotation,
    )

    if not behaviors:
        return False, (
            "No behaviors selected for classifier targets. "
            "Adjust 'included_behaviors' or set "
            "'include_all_behaviors_from_annotation=True'. "
            f"Behaviors present in this file: {', '.join(unique_behaviors)}"
        )

    try:
        labels_df = build_label_matrix(
            n_frames=n_frames,
            annotation=annotation,
            behaviors=behaviors,
            frame_offset=frame_offset,
            progress_callback=progress_callback,
        )
    except Exception as exc:
        return False, f"Failed to build label matrix: {exc}"

    if progress_callback is not None:
        progress_callback(95)

    combined = pd.concat([features_df.reset_index(drop=True), labels_df], axis=1)
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        combined.to_csv(output_csv_path, index=False)
    except Exception as exc:
        return False, f"Failed to write output CSV: {exc}"

    if progress_callback is not None:
        progress_callback(100)

    return True, (
        f"Wrote SimBA targets CSV with {len(behaviors)} behaviors and {n_frames} frames "
        f"to {output_csv_path}"
    )