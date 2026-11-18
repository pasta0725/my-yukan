#!/bin/bash
# Installs ffmpeg (and with "fonts" the Japanese font Noto Sans CJK JP) on a GitHub runner.
# 2026-11-18: the render job's install took 41 min and then hung over 30 min (usually ~1 min), while ffmpeg-only installs in
# other jobs at the same hour took 25 s. The render job was the only one downloading ~300 MB of fonts from Ubuntu's mirror
# (fonts-noto-cjk + fonts-noto-cjk-extra, every run). So:
#   fonts : from the Actions cache (~/.cache/ci-fonts, restored in seconds); on a miss, the 4 weights we use straight from the
#           Noto repo on GitHub (then cached); Ubuntu's packages only as the last resort (8 min at most).
#   ffmpeg: apt-get (8 min at most), else a static build from GitHub.
# Output is shown (not >/dev/null) with the time each part took, so a slow part can be found later.
# usage: bash tools/ci_install.sh [fonts]
set -u
t0=$(date +%s); el() { echo "$(( $(date +%s) - t0 ))s"; }
APT="timeout 480 sudo apt-get install -y -q -o Acquire::http::Timeout=20 -o Acquire::Retries=2 -o DPkg::Lock::Timeout=60"
if ! { command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null; }; then
  if $APT ffmpeg >/tmp/apt.log 2>&1; then grep -E "^(Need to get|Fetched|W:)" /tmp/apt.log; echo "ci_install: ffmpeg from apt in $(el)"
  else
    grep -E "^(Need to get|Fetched|E:|W:)" /tmp/apt.log; echo "::warning::apt-get ffmpeg was slow or failed after $(el); using a static build"
    d=$(mktemp -d)
    curl -fsSL --retry 3 --max-time 300 https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz \
      | tar -xJ -C "$d" --strip-components=2 --wildcards '*/bin/ffmpeg' '*/bin/ffprobe'
    sudo install -m755 "$d/ffmpeg" "$d/ffprobe" /usr/local/bin/; echo "ci_install: static ffmpeg in $(el)"
  fi
fi
if [ "${1:-}" = fonts ] && ! fc-list 2>/dev/null | grep -qi "Noto Sans CJK JP"; then
  C="$HOME/.cache/ci-fonts"; F="$HOME/.local/share/fonts"; mkdir -p "$C" "$F"
  for w in Regular Medium Bold Black; do
    [ -s "$C/NotoSansCJK-$w.ttc" ] || curl -fsSL --retry 3 --max-time 300 -o "$C/NotoSansCJK-$w.ttc" "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTC/NotoSansCJK-$w.ttc" || rm -f "$C/NotoSansCJK-$w.ttc"
  done
  if ls "$C"/NotoSansCJK-*.ttc >/dev/null 2>&1; then
    cp "$C"/NotoSansCJK-*.ttc "$F/"; fc-cache -f >/dev/null
    echo "ci_install: fonts ($(ls "$C" | wc -l) files, $(du -sh "$C" | cut -f1)) in $(el)"
  else
    echo "::warning::Noto fonts from GitHub failed after $(el); trying Ubuntu's packages"
    $APT fonts-noto-cjk fonts-noto-cjk-extra >/tmp/apt.log 2>&1; grep -E "^(Need to get|Fetched|E:|W:)" /tmp/apt.log; echo "ci_install: fonts from apt in $(el)"
  fi
  fc-list | grep -c "Noto Sans CJK JP" | xargs echo "Noto Sans CJK JP faces:"
fi
