#!/usr/bin/env python3
"""Transcribe locally with faster-whisper — no API key, no upload.

The API backends in whisper.py need a key and send the audio to Groq or
OpenAI. This backend runs whisper-large-v3 on the machine itself, so a local
file (an MP3 with no captions, say) transcribes for free and never leaves the
disk. On a CUDA GPU it runs far faster than realtime; on CPU it still works,
slowly, with an int8 model.

Optional dependency: `pip install faster-whisper`. When the import fails,
is_available() returns False and the caller falls back to the API backends.

Environment overrides:
  WATCH_LOCAL_MODEL    model size (default large-v3; try small/medium on CPU)
  WATCH_LOCAL_DEVICE   cuda | cpu (default: cuda when a CUDA device is visible)
"""
from __future__ import annotations

import glob
import os
import site
import sys
from pathlib import Path

DEFAULT_MODEL = os.environ.get("WATCH_LOCAL_MODEL", "large-v3")

_model_cache: dict[tuple[str, str], object] = {}


def _register_cuda_dlls() -> None:
    """Windows: make pip-installed cuBLAS/cuDNN DLLs loadable.

    The nvidia-* wheels drop their DLLs in site-packages/nvidia/*/bin, which
    is not on PATH, so ctranslate2 fails to load CUDA without this. No-op
    everywhere else.
    """
    if sys.platform != "win32":
        return
    roots = list(site.getsitepackages())
    user_site = site.getusersitepackages()
    if isinstance(user_site, str):
        roots.append(user_site)
    for root in roots:
        for dll_dir in glob.glob(os.path.join(root, "nvidia", "*", "bin")):
            try:
                os.add_dll_directory(dll_dir)
            except OSError:
                continue
            os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")


def is_available() -> bool:
    """True when faster-whisper is importable."""
    try:
        import faster_whisper  # noqa: F401
    except Exception:
        return False
    return True


def detect_device() -> tuple[str, str]:
    """Return (device, compute_type) — CUDA when visible, else CPU."""
    override = os.environ.get("WATCH_LOCAL_DEVICE")
    if override == "cuda":
        return "cuda", "float16"
    if override == "cpu":
        return "cpu", "int8"

    _register_cuda_dlls()
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception:
        pass
    return "cpu", "int8"


def describe() -> str:
    """One-line backend description for logs and the report's source label."""
    device, _ = detect_device()
    return f"local {DEFAULT_MODEL} on {device}"


def _load_model():
    device, compute_type = detect_device()
    key = (DEFAULT_MODEL, device)
    if key not in _model_cache:
        _register_cuda_dlls()
        from faster_whisper import WhisperModel

        # First call downloads the model (~3 GB for large-v3) into the
        # HuggingFace cache; later calls reuse it.
        print(
            f"[watch] loading local whisper ({DEFAULT_MODEL}, {device}) — "
            "first run downloads the model",
            file=sys.stderr,
        )
        _model_cache[key] = WhisperModel(DEFAULT_MODEL, device=device, compute_type=compute_type)
    return _model_cache[key]


def transcribe_audio_local(
    audio_path: Path,
    word_timestamps: bool = False,
    language: str | None = "en",
) -> tuple[list[dict], list[dict]]:
    """Transcribe an audio file. Returns (segments, words).

    Segments match the {start, end, text} shape the rest of the pipeline uses.
    Words is empty unless word_timestamps=True.
    """
    if not is_available():
        raise SystemExit(
            "faster-whisper is not installed. Install with: pip install faster-whisper"
        )

    model = _load_model()
    try:
        raw_segments, _info = model.transcribe(
            str(Path(audio_path).resolve()),
            language=language,
            vad_filter=True,
            beam_size=5,
            word_timestamps=word_timestamps,
        )
    except Exception as exc:
        raise SystemExit(f"local whisper failed: {type(exc).__name__}: {exc}")

    segments: list[dict] = []
    words: list[dict] = []
    # faster-whisper yields lazily — transcription happens during this loop.
    for seg in raw_segments:
        text = (seg.text or "").strip()
        if not text:
            continue
        segments.append({
            "start": round(float(seg.start or 0.0), 2),
            "end": round(float(seg.end or 0.0), 2),
            "text": text,
        })
        if word_timestamps:
            for w in getattr(seg, "words", None) or []:
                word = (w.word or "").strip()
                if not word:
                    continue
                words.append({
                    "word": word,
                    "start": round(float(w.start or 0.0), 3),
                    "end": round(float(w.end or 0.0), 3),
                })

    if not segments:
        raise SystemExit("local whisper returned no transcript segments")

    return segments, words


def transcribe_video_local(video_path: str, audio_out: Path) -> list[dict]:
    """Extract audio, then transcribe it locally. Returns segments."""
    from whisper import extract_audio

    print(f"[watch] extracting audio for local whisper ({describe()})…", file=sys.stderr)
    audio_path = extract_audio(video_path, audio_out)
    segments, _ = transcribe_audio_local(audio_path)
    print(f"[watch] transcribed {len(segments)} segments via {describe()}", file=sys.stderr)
    return segments


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: local_whisper.py <audio-or-video-path>", file=sys.stderr)
        raise SystemExit(2)
    if not is_available():
        print("faster-whisper is not installed", file=sys.stderr)
        raise SystemExit(1)

    src = Path(sys.argv[1])
    segs, _ = transcribe_audio_local(src)
    for s in segs:
        start = int(s["start"])
        print(f"[{start // 60:02d}:{start % 60:02d}] {s['text']}")
