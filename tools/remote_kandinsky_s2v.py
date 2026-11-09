# Runs INSIDE the Modal GPU container (tools/modal_avatar.py, model "kandinsky"). Kandinsky S2V 1.0 Pro distilled, HD 768x1280.
# in: /content/in/{jobs.json, <image>, <name>.wav, prompt.txt?}   out: /content/out/<name>.mp4
import json, os, subprocess, time


def sh(c):
    print("$", c[:300], flush=True); t = time.time()
    subprocess.run("set -o pipefail; " + c, shell=True, check=True, executable="/bin/bash"); print(f"  ({time.time()-t:.0f}s)", flush=True)


sh("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader")
# Their stock prompt describes a real person's teeth and skin; ours keeps the 2D anime look.
PROMPT = ("The video presents a stable medium shot of a 2D anime girl facing the camera directly, drawn in clean cel-shaded anime "
          "illustration style with consistent line art and flat colours. She talks like a lively news presenter: her mouth opens and closes "
          "clearly in sync with the speech, with natural anime mouth shapes, her head and shoulders move fluidly with the rhythm of speech, "
          "she blinks naturally and her expression is warm and confident. Plain solid green background, no camera movement.")
NEG = ("realistic photo, 3D render, photorealistic skin, changing art style, deformed face, extra fingers, blurry, flickering, "
       "background change, text, watermark")
jobs = json.load(open("/content/in/jobs.json"))
for job in jobs:
    name = job[0]; img = job[3] if len(job) > 3 and job[3] else "base_green.png"; extra = job[4] if len(job) > 4 else ""
    if not os.path.exists(f"/content/in/{name}.wav"): continue
    sh(f"cd /opt/kandy && uv run --no-sync kandy-s2v generate --config src/kandinsky_s2v/configs/s2v_pro_distill_hd.yaml --attention-engine sdpa "
       f"--audio /content/in/{name}.wav --image /content/in/{img} --out /content/out/{name}.mp4 "
       f"--prompt {json.dumps((PROMPT + ' ' + extra).strip())} --negative {json.dumps(NEG)} 2>&1 | tail -40")
sh("ls -la /content/out")
