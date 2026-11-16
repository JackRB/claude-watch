# /watch

**Give Claude a video input.** Paste a URL or a local file and Claude downloads it, looks at one frame per shot, reads a timestamped transcript, and answers your question. It then files a structured analysis report in your Obsidian vault.

```
/watch https://youtu.be/<id> what hook did they open with?
/watch ~/Movies/screen-recording.mp4 when does the UI break?
```

This is a personal fork of [taoufik123-collab/claude-watch](https://github.com/taoufik123-collab/claude-watch), itself built on [bradautomates/claude-video](https://github.com/bradautomates/claude-video). See [Credits](#credits).

## What it does

- **Scene-change frames.** `scripts/frames.py` grabs one frame per detected shot (ffmpeg `select=gt(scene,…)`), so frame count follows the edit, not the duration. Uniform sampling is the fallback for static recordings.
- **0–10 s hook microscope.** `scripts/hook.py` samples the opening at 2 fps with a word-level transcript, so the report shows what was on screen as each word landed.
- **Pacing metrics.** Shot count, cuts per minute, mean and median shot length (`scripts/pacing.py`).
- **Transcript, cheapest source first.** Native captions → local `faster-whisper` → Groq → OpenAI. Only extracted audio is uploaded, and only on the API paths.
- **A report with fill-in markers.** `scripts/report.py` writes `report.md` with `<!-- pending Claude fill: … -->` markers for TL;DR, key moments, hook, editorial profile, quotes, entities and concepts. Claude fills every marker before the report is filed.
- **Vault filing.** The report goes to `Projects/<Project>/Video Analysis/<slug>/` in the vault, picked by subject, named `<Title> — watch report.md`, and opened in Obsidian. Then Claude offers to run the vault's ingest.

`SKILL.md` is the contract Claude follows; this README is for people.

## Install (Claude Code)

```bash
git clone https://github.com/JackRB/claude-watch.git ~/.claude/skills/watch
python ~/.claude/skills/watch/scripts/setup.py
```

Use `python`, not `python3`, on Windows: `python3` there is the Microsoft Store stub.

Setup installs or prints install commands for `ffmpeg` and `yt-dlp` (brew on macOS; apt/dnf/pipx on Linux; winget/pip on Windows) and scaffolds `~/.config/watch/.env` (mode 600). `setup.py --check` exits 0 when everything is ready; the SessionStart hook stays silent in that case.

### Configuration

| Setting | Where | Default |
|---|---|---|
| `WATCH_VAULT_DIR` | environment | `~/My Drive/Obsidian/Jack` |
| `WATCH_LOCAL_MODEL` | environment | `large-v3` |
| `WATCH_LOCAL_DEVICE` | environment | auto (`cuda` or `cpu`) |
| `GROQ_API_KEY`, `OPENAI_API_KEY` | `~/.config/watch/.env` | unset: captions and local Whisper only |

### Transcription backends

| Backend | Needs | Notes |
|---|---|---|
| Native captions | `yt-dlp` | Free; covers most public videos |
| Local Whisper | `pip install faster-whisper` | No key, no upload. GPU needs `nvidia-cublas-cu12` and `nvidia-cudnn-cu12`; otherwise set `WATCH_LOCAL_DEVICE=cpu` |
| Groq | `GROQ_API_KEY` | `whisper-large-v3`; 25 MB upload cap |
| OpenAI | `OPENAI_API_KEY` | `whisper-1`; 25 MB upload cap |

`--no-whisper` turns speech fallback off; caption-less videos then come back frames-only.

## Usage

```
/watch <url-or-path> [question]
```

Flags for `scripts/watch.py`:

| Flag | Use |
|---|---|
| `--start T` / `--end T` | Focus on a section (`SS`, `MM:SS`, `HH:MM:SS`); denser frames, absolute timestamps |
| `--intent "…"` | What you want from the video; shapes the report |
| `--max-frames N` | Tighter token budget |
| `--resolution W` | Frame width (default 512; 1024 to read on-screen text) |
| `--fps F` | Override auto-fps (capped at 2; disables scene-change sampling) |
| `--whisper local\|groq\|openai` | Force a transcription backend |
| `--no-whisper` · `--no-hook-microscope` · `--no-scene-change` · `--no-dedup` | Turn a stage off |
| `--out-dir DIR` | Keep working files somewhere specific |

## Limits

- At most 100 frames and 2 fps. 80 frames at 512 px is roughly 50–80k tokens.
- Accuracy is best under 10 minutes. Past that the script warns; a focused `--start`/`--end` re-run usually beats a sparse scan.
- No logins. Public URLs and local files only.
- Keep `yt-dlp` current: site changes break old releases, usually as HTTP 403s.

## Develop

```bash
python -m unittest discover -s scripts/tests
```

See [CHANGELOG.md](CHANGELOG.md).

## Credits

The download, ffmpeg pipeline, Whisper API backends and SessionStart hook come from **[claude-video](https://github.com/bradautomates/claude-video)** by **[Bradley Bonanno](https://github.com/bradautomates)** (MIT). Scene-change frames, the hook microscope, pacing and the structured report come from **[taoufik123-collab/claude-watch](https://github.com/taoufik123-collab/claude-watch)**. This fork adds local `faster-whisper` transcription and vault filing. Contributors are listed in [AUTHORS.md](AUTHORS.md); copyright in [LICENSE](LICENSE).
