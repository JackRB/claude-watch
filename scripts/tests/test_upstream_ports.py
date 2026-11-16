"""Tests for fixes ported from bradautomates/claude-video v0.2.0-v0.3.2."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import download  # noqa: E402
import frames  # noqa: E402
import transcribe  # noqa: E402
import whisper  # noqa: E402

HAS_FFMPEG = shutil.which("ffmpeg") is not None


class VttParsingTests(unittest.TestCase):
    def _parse(self, text: str) -> list[dict]:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.vtt"
            p.write_text(text, encoding="utf-8")
            return transcribe.parse_vtt(str(p))

    def test_optional_hours_bom_entities_and_note(self):
        segs = self._parse(
            "﻿WEBVTT\n\nNOTE a comment\n00:00:09.000 --> 00:00:10.000\nnot a cue\n\n"
            "00:01.000 --> 00:02.500 align:start\nTom &amp; <c>Jerry</c>\n\n"
            "01:00:00.000 --> 01:00:01.000\nlate\n"
        )
        self.assertEqual([s["text"] for s in segs], ["Tom & Jerry", "late"])
        self.assertEqual(segs[0]["start"], 1.0)
        self.assertEqual(segs[1]["start"], 3600.0)

    def test_missing_blank_separator_keeps_next_cue(self):
        segs = self._parse(
            "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\none\n00:00:03.000 --> 00:00:04.000\ntwo\n"
        )
        self.assertEqual([s["text"] for s in segs], ["one", "two"])

    def test_rolling_duplicates_collapse(self):
        segs = self._parse(
            "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nhello\n\n"
            "00:00:02.000 --> 00:00:03.000\nhello world\n\n"
            "00:00:03.000 --> 00:00:03.010\nhello world\n"
        )
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["text"], "hello world")
        self.assertEqual(segs[0]["end"], 3.01)

    def test_repeated_speech_after_gap_survives(self):
        segs = self._parse(
            "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nyes\n\n00:00:05.000 --> 00:00:06.000\nyes\n"
        )
        self.assertEqual(len(segs), 2)


class DedupTests(unittest.TestCase):
    def test_drops_frames_close_to_last_kept(self):
        with tempfile.TemporaryDirectory() as d:
            paths = []
            for i in range(4):
                p = Path(d) / f"frame_{i:04d}.jpg"
                p.write_bytes(b"x")
                paths.append(p)
            fs = [{"index": i, "timestamp_seconds": i, "path": str(p)} for i, p in enumerate(paths)]
            size = frames.DEDUP_THUMB * frames.DEDUP_THUMB * 3
            thumbs = [bytes([0]) * size, bytes([1]) * size, bytes([200]) * size, bytes([201]) * size]
            kept, dropped = frames.dedupe_by_deltas(fs, thumbs)
            self.assertEqual(dropped, 2)
            self.assertEqual([f["timestamp_seconds"] for f in kept], [0, 2])
            self.assertEqual([f["index"] for f in kept], [0, 1])
            self.assertFalse(paths[1].exists())
            self.assertTrue(paths[2].exists())

    def test_misaligned_thumbs_fail_open(self):
        fs = [{"index": 0, "path": "a"}, {"index": 1, "path": "b"}]
        kept, dropped = frames.dedupe_by_deltas(fs, [])
        self.assertEqual((kept, dropped), (fs, 0))

    @unittest.skipUnless(HAS_FFMPEG, "ffmpeg not installed")
    def test_real_frames_identical_dropped(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            for i, color in enumerate(["red", "red", "blue"]):
                subprocess.run(
                    ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                     "-i", f"color=c={color}:s=64x64", "-frames:v", "1", str(out / f"frame_{i:04d}.jpg")],
                    check=True,
                )
            fs = [{"index": i, "timestamp_seconds": i, "path": str(out / f"frame_{i:04d}.jpg")} for i in range(3)]
            kept, dropped = frames.dedupe_frames(fs)
            self.assertEqual(dropped, 1)
            self.assertEqual([f["timestamp_seconds"] for f in kept], [0, 2])


class SyncOptionTests(unittest.TestCase):
    def _detect(self, help_text: str) -> tuple[str, str]:
        frames._sync_option.cache_clear()
        fake = subprocess.CompletedProcess([], 0, stdout=help_text, stderr="")
        with mock.patch.object(frames.subprocess, "run", return_value=fake):
            try:
                return frames._sync_option("ffmpeg-fake")
            finally:
                frames._sync_option.cache_clear()

    def test_ffmpeg9_stream_spec_format(self):
        self.assertEqual(self._detect("  -fps_mode[:<stream_spec>] <string>  set mode\n"), ("-fps_mode", "vfr"))

    def test_older_ffmpeg_falls_back_to_vsync(self):
        self.assertEqual(self._detect("-vsync <string>  set video sync method\n"), ("-vsync", "vfr"))


class WhisperChunkTests(unittest.TestCase):
    def test_plan_fits_in_one(self):
        self.assertEqual(whisper.plan_chunks(600.0, 1_000_000), [(0.0, 600.0)])

    def test_plan_splits_evenly_and_sums(self):
        plan = whisper.plan_chunks(3600.0, 50_000_000, 24_000_000)
        self.assertEqual(len(plan), 3)
        self.assertAlmostEqual(sum(d for _, d in plan), 3600.0, places=2)
        self.assertEqual(plan[1][0], 1200.0)

    def test_chunks_shift_and_tolerate_one_failure(self):
        calls = []

        def one(path):
            calls.append(path)
            if path == "b":
                raise SystemExit("boom")
            return [{"start": 1.0, "end": 2.0, "text": path}]

        segs = whisper.transcribe_chunks([("a", 0.0), ("b", 100.0), ("c", 200.0)], one)
        self.assertEqual([(s["start"], s["text"]) for s in segs], [(1.0, "a"), (201.0, "c")])

    def test_all_chunks_failing_raises(self):
        def one(path):
            raise SystemExit("boom")

        with self.assertRaises(SystemExit):
            whisper.transcribe_chunks([("a", 0.0), ("b", 10.0)], one)


class DownloadHintTests(unittest.TestCase):
    def test_403_says_update_ytdlp(self):
        self.assertIn("out of date", download.failure_hint("ERROR: HTTP Error 403: Forbidden"))

    def test_403_inside_number_not_matched(self):
        self.assertNotIn("403", download.failure_hint("ERROR: id 14031 unavailable"))

    def test_rate_limit(self):
        self.assertIn("rate limiting", download.failure_hint("HTTP Error 429: Too Many Requests"))


if __name__ == "__main__":
    unittest.main()
