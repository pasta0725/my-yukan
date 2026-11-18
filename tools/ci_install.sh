#!/bin/bash
# Installs ffmpeg (and with "fonts" the Noto CJK fonts) on a GitHub runner.
# 2026-11-18: apt-get on the runner took 41 min and then hung over 30 min (usually ~1 min),
# so apt-get gets 8 min at most; after that, ffmpeg comes from a static build and the fonts from the Noto repo on GitHub.
# usage: bash tools/ci_install.sh [fonts]
set -u
want_fonts=0; [ "${1:-}" = fonts ] && want_fonts=1
pkgs=""
{ command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null; } || pkgs="ffmpeg"
if [ $want_fonts = 1 ] && ! fc-list 2>/dev/null | grep -qi "Noto Sans CJK"; then pkgs="$pkgs fonts-noto-cjk fonts-noto-cjk-extra"; fi
[ -z "$pkgs" ] && exit 0
start=$(date +%s)
if timeout 480 sudo apt-get install -y -qq -o Acquire::http::Timeout=20 -o Acquire::Retries=2 -o DPkg::Lock::Timeout=60 $pkgs >/dev/null; then
  echo "ci_install: apt-get ok in $(( $(date +%s) - start ))s"; exit 0
fi
echo "::warning::apt-get took too long or failed after $(( $(date +%s) - start ))s; using the fallbacks"
if ! { command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null; }; then
  d=$(mktemp -d)
  curl -fsSL --retry 3 --max-time 300 https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz \
    | tar -xJ -C "$d" --strip-components=2 --wildcards '*/bin/ffmpeg' '*/bin/ffprobe'
  sudo install -m755 "$d/ffmpeg" "$d/ffprobe" /usr/local/bin/
  ffmpeg -hide_banner -version | head -1
fi
if [ $want_fonts = 1 ] && ! fc-list 2>/dev/null | grep -qi "Noto Sans CJK"; then
  mkdir -p "$HOME/.local/share/fonts"
  for w in Regular Medium Bold Black; do
    curl -fsSL --retry 3 --max-time 300 -o "$HOME/.local/share/fonts/NotoSansCJK-$w.ttc" "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTC/NotoSansCJK-$w.ttc"
  done
  fc-cache -f >/dev/null; fc-list | grep -c "Noto Sans CJK JP"
fi
