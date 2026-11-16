#!/usr/bin/env python3
"""Parse a WebVTT subtitle file into a clean, timestamped transcript.

YouTube auto-subs emit rolling-duplicate cues (each line appears 2-3 times as it
scrolls). We collapse a cue into the previous one only when they touch or
overlap in time and share cue settings, so genuinely repeated speech survives.

WebVTT handling ported from bradautomates/claude-video v0.3.0: optional hours,
BOM, HTML entities, NOTE/STYLE/REGION blocks, and a missing blank line between cues.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path


TIME = r"(?:\d{2,}:)?[0-5]\d:[0-5]\d[.,]\d{3}"
TS_RE = re.compile(rf"^\s*({TIME})\s+-->\s+({TIME})(?:\s+.*)?$")
BLOCK_RE = re.compile(r"^(NOTE(?:\s|$)|STYLE$|REGION$)")
TAG_RE = re.compile(r"<[^>]*>")


def _to_seconds(stamp: str) -> float:
    parts = stamp.replace(",", ".").split(":")
    return sum(float(p) * 60 ** i for i, p in enumerate(reversed(parts)))


def parse_vtt(path: str) -> list[dict]:
    text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    lines = text.splitlines()

    segments: list[dict] = []
    i = 0
    while i < len(lines):
        if BLOCK_RE.match(lines[i]):
            i += 1
            while i < len(lines) and lines[i].strip():
                i += 1
            continue
        match = TS_RE.match(lines[i])
        if not match:
            i += 1
            continue

        start = _to_seconds(match.group(1))
        end = _to_seconds(match.group(2))
        settings = lines[i][match.end(2):].strip()
        i += 1

        cue_lines: list[str] = []
        while i < len(lines) and lines[i].strip():
            if TS_RE.match(lines[i]):  # missing blank separator: next cue starts here
                break
            cleaned = html.unescape(TAG_RE.sub("", lines[i])).strip()
            if cleaned:
                cue_lines.append(cleaned)
            i += 1

        cue_text = " ".join(cue_lines).strip()
        if cue_text and end >= start:
            segments.append({
                "start": round(start, 2), "end": round(end, 2),
                "text": cue_text, "_settings": settings,
            })

    return [{k: s[k] for k in ("start", "end", "text")} for s in _dedupe(segments)]


def _dedupe(segments: list[dict]) -> list[dict]:
    """Collapse rolling duplicates common in YouTube auto-subs."""
    out: list[dict] = []
    for seg in segments:
        prev = out[-1] if out else None
        if (
            prev is not None
            and seg["start"] <= prev["end"]
            and seg["_settings"] == prev["_settings"]
            and (seg["text"] == prev["text"] or seg["text"].startswith(prev["text"] + " "))
        ):
            prev["text"] = seg["text"]
            prev["end"] = max(prev["end"], seg["end"])
            continue
        out.append(dict(seg))
    return out


def filter_range(
    segments: list[dict],
    start_seconds: float | None,
    end_seconds: float | None,
) -> list[dict]:
    """Return segments whose time range overlaps [start, end]."""
    if start_seconds is None and end_seconds is None:
        return segments
    lo = start_seconds if start_seconds is not None else float("-inf")
    hi = end_seconds if end_seconds is not None else float("inf")
    return [seg for seg in segments if seg["end"] >= lo and seg["start"] <= hi]


def format_transcript(segments: list[dict]) -> str:
    lines = []
    for seg in segments:
        start = int(seg["start"])
        stamp = f"[{start // 60:02d}:{start % 60:02d}]"
        lines.append(f"{stamp} {seg['text']}")
    return "\n".join(lines)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: transcribe.py <vtt-path>", file=sys.stderr)
        raise SystemExit(2)
    print(format_transcript(parse_vtt(sys.argv[1])))
