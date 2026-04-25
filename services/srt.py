"""Parse DJI drone SRT metadata files.

DJI SRT files contain per-frame telemetry — GPS position, altitude,
focal length, exposure. We extract the bits relevant to COLMAP camera
intrinsics estimation (focal length) plus position info that future
work may use as a reconstruction prior.

Pure module: no bpy dependency.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# Block separator: a blank line. Each block has 4 lines:
#   <index>
#   <timecode --> timecode>
#   <html-wrapped metadata line 1 (counter)>
#   <metadata line 2 (timestamp)>
#   <metadata line 3 (bracketed key:value pairs)>
# But formats vary. We just look for the bracketed metadata anywhere
# in the block and the leading integer index.

_KV_RE = re.compile(r"\[(\w+)\s*:\s*([^\]]+?)\]")
_INDEX_RE = re.compile(r"^\s*(\d+)\s*$", re.MULTILINE)


def parse_srt_metadata(srt_path: Path) -> dict[str, Any] | None:
    """Parse a DJI SRT file. Returns None if missing/empty/unparseable.

    Returns a dict:
      {
        "focal_len_mm": float,           # from the first frame
        "frames": [
          {"frame_index": int,
           "focal_len_mm": float | None,
           "latitude": float | None,
           "longitude": float | None,
           "rel_alt": float | None,
           "abs_alt": float | None},
           ...
        ],
      }
    """
    srt_path = Path(srt_path)
    if not srt_path.exists():
        return None
    raw = srt_path.read_text(errors="replace")
    if not raw.strip():
        return None

    blocks = [b for b in raw.split("\n\n") if b.strip()]
    frames: list[dict[str, Any]] = []
    for block in blocks:
        index_match = _INDEX_RE.search(block)
        if not index_match:
            continue
        kv = {m.group(1).lower(): m.group(2).strip() for m in _KV_RE.finditer(block)}
        if not kv:
            continue
        # Some DJI SRTs cram multiple values into a single bracket like
        # "[rel_alt: 50.0 abs_alt: 1650.0]" — split those on spaces.
        for key in list(kv.keys()):
            val = kv[key]
            if " " in val and ":" in val:
                # Re-split: "50.0 abs_alt: 1650.0" → rel_alt=50.0, abs_alt=1650.0
                head, _, tail = val.partition(" ")
                kv[key] = head
                # tail is "abs_alt: 1650.0" — re-parse
                tail_match = re.match(r"(\w+)\s*:\s*([\d.\-]+)", tail)
                if tail_match:
                    kv[tail_match.group(1).lower()] = tail_match.group(2)

        focal_raw = _safe_float(kv.get("focal_len"))
        focal_mm = focal_raw / 10.0 if focal_raw is not None else None
        frames.append(
            {
                "frame_index": int(index_match.group(1)),
                "focal_len_mm": focal_mm,
                "latitude": _safe_float(kv.get("latitude")),
                "longitude": _safe_float(kv.get("longitude")),
                "rel_alt": _safe_float(kv.get("rel_alt")),
                "abs_alt": _safe_float(kv.get("abs_alt")),
            }
        )

    if not frames:
        return None

    return {
        "focal_len_mm": frames[0]["focal_len_mm"],
        "frames": frames,
    }


def _safe_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None
