"""Talking-presenter clips on Modal (cloud GPUs that are almost always free; $30/month free credit, no card).
Same input folder as longcat-colab.yml: jobs.json ([[name, segments, res, image, extra_prompt], ...]), the images,
<name>.wav and optionally prompt.txt. Runs one of three image+voice -> talking-video AIs and saves <out>/<name>.mp4.

  modal run tools/modal_avatar.py --dir shorts/rina_zelda/longcat --model longcat --out /tmp/out
  models: longcat    LongCat-Video-Avatar 1.5, 8-step distilled (what we use on Colab; tools/colab_longcat_remote.py)
          kandinsky  Kandinsky S2V 1.0 Pro distilled HD (Oct 2026; tools/remote_kandinsky_s2v.py)
          echomimic  EchoMimicV3-Flash (Jan 2026; tools/remote_echomimic3.py)
GPUs: A100 80GB for LongCat (about $2.5/h, peak ~47 GB), H100 for Kandinsky (its flash-attention 3 needs Hopper), L40S 48GB for EchoMimic.
Weights are kept in the Modal volume "rina-avatar-weights", so only the first run of each model downloads them.
Each remote script is the Colab-style runner: reads /content/in, writes /content/out/<name>.mp4, keeps weights in /content/w."""
import os, pathlib
import modal

app = modal.App("rina-avatar")
vol = modal.Volume.from_name("rina-avatar-weights", create_if_missing=True)
SYS = ["git", "ffmpeg", "libgl1", "libglib2.0-0", "libsndfile1"]

img_longcat = (modal.Image.debian_slim(python_version="3.12").apt_install(*SYS)
               .pip_install("torch==2.8.0", "torchvision==0.23.0", "torchaudio==2.8.0", "numpy<2.3", "scipy", "opencv-python-headless",
                            "pillow", "accelerate", "safetensors", "sentencepiece", "psutil", "huggingface_hub[hf_transfer]<1.0"))
img_kandinsky = (modal.Image.debian_slim(python_version="3.13").apt_install(*SYS).pip_install("uv", "huggingface_hub[hf_transfer]")
                 .run_commands("git clone -q --depth 1 https://github.com/kandinskylab/kandinsky-s2v /opt/kandy && cd /opt/kandy && uv sync --no-dev"))
img_echomimic = (modal.Image.debian_slim(python_version="3.11").apt_install(*SYS)
                 .pip_install("torch==2.6.0", "torchvision==0.21.0", "torchaudio==2.6.0", "huggingface_hub[hf_transfer]<1.0")
                 .run_commands("git clone -q --depth 1 https://github.com/antgroup/echomimic_v3 /opt/em3 && cd /opt/em3 && "
                               "grep -viE '^(tensorflow|retina-face|gradio|tensorboard|torch)' requirements.txt > /tmp/req.txt && pip install -q -r /tmp/req.txt"))

RUNNERS = {"longcat": "colab_longcat_remote.py", "kandinsky": "remote_kandinsky_s2v.py", "echomimic": "remote_echomimic3.py"}


def _run(files: dict, script: str) -> dict:
    import subprocess
    os.makedirs("/content/in", exist_ok=True); os.makedirs("/content/out", exist_ok=True)
    if not os.path.islink("/content/w"):
        os.symlink("/vol", "/content/w")             # weights live in the volume
    for n, b in files.items():
        open(f"/content/in/{n}", "wb").write(b)
    open("/content/run.py", "w").write(script)
    env = dict(os.environ, HF_HUB_ENABLE_HF_TRANSFER="1", HF_HOME="/vol/hf")
    r = subprocess.run(["python", "/content/run.py"], cwd="/content", env=env)
    vol.commit()                                      # keep downloaded weights even if the run failed
    out = {}
    for p in pathlib.Path("/content/out").glob("*.mp4"):
        out[p.name] = p.read_bytes()
    for d in pathlib.Path("/content/out").glob("*/"):  # runners that write /content/out/<name>/... (LongCat)
        v = sorted(d.rglob("*.mp4"), key=lambda q: q.stat().st_mtime)
        if v and f"{d.name}.mp4" not in out: out[f"{d.name}.mp4"] = v[-1].read_bytes()
    print("exit", r.returncode, "clips", list(out), flush=True)
    return out


@app.function(image=img_longcat, gpu="A100-80GB", volumes={"/vol": vol}, timeout=3 * 3600)
def longcat(files: dict, script: str) -> dict:
    return _run(files, script)


@app.function(image=img_kandinsky, gpu="H100", volumes={"/vol": vol}, timeout=3 * 3600)
def kandinsky(files: dict, script: str) -> dict:
    return _run(files, script)


@app.function(image=img_echomimic, gpu="L40S", volumes={"/vol": vol}, timeout=3 * 3600)
def echomimic(files: dict, script: str) -> dict:
    return _run(files, script)


@app.local_entrypoint()
def main(dir: str, model: str = "longcat", out: str = "/tmp/out"):
    here = pathlib.Path(__file__).parent
    files = {p.name: p.read_bytes() for p in pathlib.Path(dir).iterdir() if p.is_file()}
    script = (here / RUNNERS[model]).read_text()
    fn = {"longcat": longcat, "kandinsky": kandinsky, "echomimic": echomimic}[model]
    res = fn.remote(files, script)
    os.makedirs(out, exist_ok=True)
    for n, b in res.items():
        open(os.path.join(out, n), "wb").write(b); print("saved", n, len(b))
    if not res: raise SystemExit("no clip")
