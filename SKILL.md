---
name: watch
description: Watch a video (URL or local path) like an editor. Extracts scene-change frames, pacing metrics (cuts/min, shot length), and a dense 0-10s hook microscope; pulls transcript from captions or Whisper. Files an analysis report in the Obsidian vault next to the project it's about, and offers to ingest it — tied to *why* the user watched it.
argument-hint: "<video-url-or-path> [why you're watching it]"
allowed-tools: Bash, Read, Edit, Write, AskUserQuestion
homepage: https://github.com/JackRB/claude-watch
repository: https://github.com/JackRB/claude-watch
author: taoufik (upstream), Jack (fork)
license: MIT
user-invocable: true
---

# /watch — Claude watches a video

You have no video input; this skill gives you one. `scripts/watch.py` downloads the video, extracts one frame per detected shot, gets a timestamped transcript, computes pacing metrics, samples the first 10 seconds densely, and writes `<workdir>/report.md` with `<!-- pending Claude fill: ... -->` markers. You read the frames, answer the user, fill the report, and file it in the vault.

On Windows run `python`, not `python3` (`python3` is the Microsoft Store stub).

## 0. Preflight

```bash
python "${CLAUDE_SKILL_DIR}/scripts/setup.py" --check
```

Exit 0 prints nothing; go on without comment. Skip this on later `/watch` calls in the same session. Otherwise:

| Exit | Meaning | Fix |
|---|---|---|
| 2 | `ffmpeg` / `ffprobe` / `yt-dlp` missing | `python "${CLAUDE_SKILL_DIR}/scripts/setup.py"` (idempotent; prints install commands on Windows) |
| 3 | No transcription backend | `pip install faster-whisper` (local, free, no upload); or ask for a Groq or OpenAI key and write it to `~/.config/watch/.env` as `GROQ_API_KEY=` / `OPENAI_API_KEY=` |
| 4 | Both | Both fixes |

If the user wants no backend, run with `--no-whisper`: videos without captions come back frames-only.

## 1. Run the script

Split the input into the source and the question. The question is the intent; with none, use a short inferred one ("general summary"). The intent shapes the report's TL;DR, entities and concepts.

```bash
python "${CLAUDE_SKILL_DIR}/scripts/watch.py" "<source>" --intent "<intent>"
```

| Flag | Use |
|---|---|
| `--start T` / `--end T` | Focus on a section (`SS`, `MM:SS`, `HH:MM:SS`). Use it whenever the user names a moment, and for videos over ~10 min where the question is about one part. Denser frames; transcript is filtered to the range; timestamps stay absolute. |
| `--max-frames N` | Tighter token budget |
| `--resolution W` | Frame width, default 512. 1024 only to read on-screen text (~4× the tokens). |
| `--fps F` | Override auto-fps; capped at 2; disables scene-change sampling |
| `--whisper local\|groq\|openai` | Force a backend |
| `--no-whisper` · `--no-hook-microscope` · `--no-scene-change` | Turn a stage off |
| `--out-dir DIR` | Keep working files somewhere specific |

Frame budget is automatic: at most 100 frames and 2 fps. Accuracy is best under 10 minutes; past that the script warns, and a focused re-run usually beats a sparse scan. 80 frames at 512 px is roughly 50–80k tokens.

Transcript order: native captions → local `faster-whisper` (`WATCH_LOCAL_MODEL`, default `large-v3`; `WATCH_LOCAL_DEVICE=cuda|cpu`) → Groq → OpenAI. Only the extracted audio is ever uploaded, and only on the API paths.

## 2. Look, answer, fill

1. **Read every frame path the script lists**, all in one message. Frames are chronological, labeled `t=MM:SS`.
2. **Answer the user's question** in chat, citing timestamps.
3. **Fill every pending marker in `report.md`** with Edit:
   - TL;DR — 3–5 bullets through the intent
   - Key moments — 5–10 timestamped bullets
   - Hook microscope — visual change × what's said; name the hook pattern
   - Editorial profile — one line from the pacing numbers and hero frames
   - Quotable moments — 3–5 standalone lines
   - Entities and Concepts — Title Case `[[wikilinks]]` (people, companies, tools, places; frameworks and named patterns with a short gist)

A report with unfilled markers is not finished; don't file or ingest it.

Follow-up questions on the same video: answer from what's in context; don't re-run the script.

## 3. File it in the vault

The vault is `$WATCH_VAULT_DIR` if set, else `~/My Drive/Obsidian/Jack`. Its `CLAUDE.md` governs; read it if this session hasn't.

1. **Pick the project by subject, not format**: list `Projects/` and choose the folder the video is about (a Medicare video → `Retirement`). Nothing fits → ask; don't invent a folder.
2. **Folder:** `Projects/<Project>/Video Analysis/<slug>/`, where slug = the title slugified (lowercase, ASCII, hyphens, ≤60 chars) + `-YYYY-MM-DD`.
3. **Copy in** the filled report and every frame named in its `hero_frames:` frontmatter. **Name the report `<Title> — watch report.md`**, so `[[Title — watch report]]` resolves. Strip characters Windows forbids in filenames (`\ / : * ? " < > |`).
4. **Open it** in Obsidian:
   ```powershell
   Start-Process "obsidian://open?vault=Jack&file=<vault-relative path, spaces as %20>"
   ```
   and echo the vault-relative path in chat on its own line.

## 4. Offer ingest — once

`AskUserQuestion`: "Ingest this into the vault?"

- **Yes** → run `/ingest` on the filed report (the vault's Ingest op: links, ripple to doctrine, Open Loops). If the user gives a different angle, rewrite TL;DR, Entities and Concepts for it first.
- **Leave it filed** → done; it can be ingested later.
- **Drop it** → delete the `<slug>/` folder from the vault.

Then delete the script's working directory, unless follow-up questions are likely.

## Failure modes

- **Download fails** (login-required, region-locked) → say so plainly; don't retry.
- **No transcript** → proceed frames-only and say so.
- **Whisper API fails** (bad key, rate limit, 25 MB limit) → retry with the other API, or `--whisper local`, which has no size limit.
- **Local Whisper fails** (usually `cublas64_12.dll` not found) → `WATCH_LOCAL_DEVICE=cpu` with a smaller `WATCH_LOCAL_MODEL`, or an API backend. CUDA libraries come from `nvidia-cublas-cu12` / `nvidia-cudnn-cu12`.
- **Ingest fails partway** → don't roll back; leave the report filed and tell the user what failed. `/ingest` can be re-run.

## What it touches

- Network: the video host (yt-dlp); HuggingFace once, for local model weights; Groq or OpenAI only when transcribing by API — each key goes only to its own provider.
- Disk: a temp working directory (or `--out-dir`), `~/.config/watch/.env` (keys, mode 0600, never echoed), and the vault folder from step 3.
- No accounts, cookies or posting.

Scripts: `scripts/watch.py` (entry), `download.py`, `frames.py`, `pacing.py`, `hook.py`, `report.py`, `transcribe.py`, `whisper.py`, `local_whisper.py`, `setup.py`.
