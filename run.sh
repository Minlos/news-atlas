#!/bin/bash
set -euo pipefail
export PATH="/usr/local/bin:${HOME}/.local/bin:/usr/bin:/bin"
ROOT="${HOME}/news-atlas"
OUT="${HOME}/minlos.site/news"
cd "$ROOT"
mkdir -p "$OUT" logs
export OUT_DIR="$OUT"
exec 9>run.lock
if ! flock -n 9; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) skip: already running" >> logs/run.log
  exit 0
fi
{
  echo "==== $(date -u +%Y-%m-%dT%H:%M:%SZ) ===="
  python3 build.py
  echo "ok $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} >> logs/run.log 2>&1
