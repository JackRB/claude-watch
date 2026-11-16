#!/usr/bin/env bash
# SessionStart hook for /watch. Silent when setup.py --check passes (media
# tools present and a transcription backend available: local faster-whisper or
# an API key). Otherwise one line pointing at the installer.
set -uo pipefail

CONFIG_FILE="$HOME/.config/watch/.env"
SETUP_PY="$(cd "$(dirname "$0")/../../scripts" && pwd)/setup.py"

# Warn if the secrets file has loose permissions.
if [[ -f "$CONFIG_FILE" ]]; then
  perms=$(stat -c '%a' "$CONFIG_FILE" 2>/dev/null || stat -f '%Lp' "$CONFIG_FILE" 2>/dev/null || echo "")
  if [[ -n "$perms" && "$perms" != "600" && "$perms" != "400" ]]; then
    echo "/watch: WARNING: $CONFIG_FILE has permissions $perms (should be 600). Fix: chmod 600 $CONFIG_FILE"
  fi
fi

# `python` first: on Windows `python3` is the Microsoft Store stub.
PY="$(command -v python || command -v python3 || true)"
if [[ -z "$PY" ]]; then
  echo "/watch: Python not found on PATH."
  exit 0
fi

"$PY" "$SETUP_PY" --check >/dev/null 2>&1
case $? in
  0) exit 0 ;;
  2) echo "/watch: needs ffmpeg + yt-dlp. Run \`$PY \"$SETUP_PY\"\` to install." ;;
  3) echo "/watch: captions only. pip install faster-whisper (local), or add GROQ_API_KEY / OPENAI_API_KEY to ~/.config/watch/.env, for videos without captions." ;;
  *) echo "/watch: needs ffmpeg + yt-dlp and a transcription backend. Run \`$PY \"$SETUP_PY\"\`." ;;
esac
exit 0
