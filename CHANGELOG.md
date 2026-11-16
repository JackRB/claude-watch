# Changelog

All notable changes to `/watch` are documented here.

## [0.3.1] — 2026-11-16 (JackRB fork)

Fixes ported from upstream [bradautomates/claude-video](https://github.com/bradautomates/claude-video) v0.2.0–v0.3.2, adapted to this fork's flat `scripts/` layout.

### Added
- Frame dedup (default on, `--no-dedup` to keep all). Frames within a mean 2/255 of the last kept frame (16×16 RGB thumbnail) are dropped after pacing is computed, so cut counts stay exact. The **Frames** line reports how many were dropped.
- Whisper auto-chunking for Groq/OpenAI: audio over 24 MB (~50 min) is split into even chunks, timestamps are shifted back, and one failed chunk no longer loses the transcript. Local faster-whisper is unaffected.
- yt-dlp failure hints: a 403 says to update yt-dlp and retry once; 429 and sign-in errors get their own hint.

### Fixed
- ffmpeg sync flag is detected: `-fps_mode vfr` when advertised (including FFmpeg 9's `-fps_mode[:<stream_spec>]` help format), else `-vsync vfr`.
- WebVTT parsing: optional hours, BOM, HTML entities, NOTE/STYLE/REGION blocks, and cues missing a blank separator. Rolling-duplicate collapse now needs touching or overlapping cues with the same settings, so repeated speech after a gap survives.

### Not ported
- Gemini engine, WhisperX/uv, `--detail` modes, `--timestamps`, caption-language selection, and the `skills/watch/` restructure. The fork has local faster-whisper and vault filing instead.

## [0.3.0] — 2026-11-16 (JackRB fork)

### Added
- Local transcription with `faster-whisper` (`scripts/local_whisper.py`), tried after native captions and before Groq/OpenAI. No key, no upload. `WATCH_LOCAL_MODEL`, `WATCH_LOCAL_DEVICE`.
- Vault filing: reports go to `Projects/<Project>/Video Analysis/<slug>/` as `<Title> — watch report.md`, with `type: watch-report` frontmatter, then an ingest offer.

### Changed
- `SKILL.md` simplified to the procedure; the vault defaults to `~/My Drive/Obsidian/Jack` when `WATCH_VAULT_DIR` is unset.
- `allowed-tools` adds Edit and Write, which the fill and filing steps use.
- The SessionStart hook runs `setup.py --check` and is silent when it passes, so an install with local Whisper no longer gets an API-key hint each session. The hook path is quoted.
- Setup hints name the running interpreter instead of `python3`, which is the Microsoft Store stub on Windows.
- README, AUTHORS and plugin metadata describe this fork.

### Fixed
- UTF-8 stdout/stderr on Windows consoles.

## [0.2.0] — 2026-05-25

Based on [bradautomates/claude-video](https://github.com/bradautomates/claude-video) v0.1.3 by Bradley Bonanno (MIT). Its pipeline (yt-dlp + ffmpeg + Whisper) is preserved; everything below is additive.

### Added
- Scene-change frame extraction in `scripts/frames.py` — `extract_scene_change()` + `select_hero_frames()` using ffmpeg's `select=gt(scene,...)` filter. One frame per detected shot instead of uniform every-N-seconds sampling. Keeps token cost flat on long videos. Uniform sampling still available as a fallback for static/screen-recorded sources.
- 0-10s hook microscope in `scripts/hook.py` — 2 fps frames + word-level Whisper transcript on the opening 10 seconds, so the report can tell you what's on screen *as each word lands*.
- Editorial pacing metrics in `scripts/pacing.py` — shot count, cuts/min, mean + median shot length.
- Structured `report.md` emitter in `scripts/report.py` — fixed-schema ingest-ready report with `<!-- pending Claude fill: ... -->` markers for narrative sections (TL;DR, key moments, hook breakdown, editorial profile, quotable moments, entities, concepts).
- Word-level timestamps in `scripts/whisper.py` (Groq + OpenAI backends extended).
- New CLI flags in `scripts/watch.py`: `--intent`, `--no-scene-change`, `--no-hook-microscope`.
- Step 4.4 (stage to Obsidian vault) + Step 4.5 (ingest gate) in `SKILL.md` — optional auto-save to your Obsidian vault. Path resolved via `$WATCH_VAULT_DIR` or auto-detected from `~/Second brain/`, `~/Documents/Obsidian/`, `~/Obsidian/`. Skips cleanly when no vault is detected.
- 7 unit tests under `scripts/tests/` (stdlib `unittest`, no pytest dependency).

### Changed
- `SKILL.md` is now a v2 contract — describes the structured report, the marker-fill step, and the vault config. Backwards-compatible with /watch invocations that don't care about ingest.
- README documents the added features and the `$WATCH_VAULT_DIR` configuration.

## [0.1.3] — 2026-05-09

### Fixed
- Windows: `video.info.json` is read as UTF-8 (#4). Previously `Path.read_text()` defaulted to cp1252 on Windows and crashed on yt-dlp's UTF-8 output, silently dropping Title/Uploader from the report. Same fix applied to `.env` reads/writes in `whisper.py` and `setup.py`.
- `download.py` now logs info.json parse failures to stderr instead of swallowing them.

### Security
- Hardened subprocess argv against option injection (#2): inserted `--` before the URL in the yt-dlp argv, and tightened `is_url` to reject `-`-prefixed sources and require a non-empty netloc. Resolved video/audio paths to absolute via `Path.resolve()` before passing to `ffmpeg`/`ffprobe`, so a relative path starting with `-` can't be misinterpreted as a flag.

## [0.1.2] — 2026-04-24

### Fixed
- Windows console crash: removed the emoji from the long-video warning in `watch.py`; cp1252 consoles couldn't encode it.
- `setup.py` now prints `winget` / `pip` install commands on Windows instead of "unsupported platform" — matches what the README already promised.

### Changed
- `SKILL.md` notes that on Windows the scripts must be invoked with `python`, not `python3` (the latter is the Microsoft Store stub on Windows).

## [0.1.1] — 2026-04-24

### Fixed
- Added `commands/watch.md` shim so `/watch` is callable when installed as a Claude Code plugin. Without it, the plugin loaded but the skill wasn't exposed as a slash command.
- `scripts/build-skill.sh` now strips `commands/` from the claude.ai `.skill` bundle alongside `hooks/` and `.claude-plugin/`.

## [0.1.0] — 2026-04-24

Initial marketplace release.

### Added
- `/watch <url-or-path> [question]` slash command.
- yt-dlp download with native caption extraction (manual + auto-subs).
- ffmpeg frame extraction with auto-scaled fps (≤2 fps, ≤100 frames, duration-aware budget).
- `--start` / `--end` focused mode with denser frame budget and transcript range filtering.
- Whisper fallback (Groq preferred, OpenAI secondary) for videos without captions.
- `setup.py` preflight: silent `--check`, structured `--json`, and installer that auto-runs `brew install` on macOS.
- Session-start hook that prints a one-line status on first run / partial config.
- `.skill` bundle packaging for claude.ai upload via `scripts/build-skill.sh`.
