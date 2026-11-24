#!/usr/bin/env bash
# Fetch the MIT-licensed instagram-agent-skill (Jake Schincariol) at a pinned
# commit into third_party/, and expose its skills to Claude Code (.claude/skills).
# Pinned so a change upstream can never silently alter the pipeline.
set -euo pipefail
REPO="https://github.com/Jakeschincariol/instagram-agent-skill.git"
SHA="d03c56bb598be770c60b201f94237e5d1a4268a6"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/third_party/instagram-agent-skill"

if [ ! -f "$DEST/LICENSE" ]; then
  rm -rf "$DEST"
  mkdir -p "$DEST"
  git -C "$DEST" init -q
  git -C "$DEST" remote add origin "$REPO"
  git -C "$DEST" fetch -q --depth 1 origin "$SHA"
  git -C "$DEST" checkout -q FETCH_HEAD
  rm -rf "$DEST/.git"
fi

mkdir -p "$ROOT/.claude/skills"
for d in "$DEST"/skills/ig-*; do
  ln -sfn "../../third_party/instagram-agent-skill/skills/$(basename "$d")" "$ROOT/.claude/skills/$(basename "$d")"
done
echo "instagram-agent-skill ready at ${SHA:0:7} ($(ls "$DEST/skills" | wc -l) skills)"
