#!/bin/bash
# Run Wan2.2-S2V on a Colab GPU (Google AI Pro compute units) from GitHub Actions. Needs GOOGLE_APPLICATION_CREDENTIALS.
set -e
GPU=${GPU:-A100}
C="colab --auth=adc"
$C usage || true
$C new -s s2v --gpu $GPU
trap '$C usage || true; $C stop -s s2v || true' EXIT
echo 'import os; os.makedirs("/content/in", exist_ok=True); print("ready")' | $C exec -s s2v --timeout 0
for f in base_green.png intro.wav verdict.wav; do $C upload -s s2v s2v/$f /content/in/$f; done
$C exec -s s2v --timeout 0 -f tools/colab_s2v_remote.py
for n in intro verdict; do $C download -s s2v /content/out/$n.mp4 s2v/$n.mp4 || true; done
