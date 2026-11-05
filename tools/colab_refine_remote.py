# Runs INSIDE a Colab GPU runtime. Cleans up the talking-character clips made by LongCat:
#   1) Real-ESRGAN "animevideov3" (anime video model, removes compression blocks): x4 inside the model, then
#      area-downscaled to the size the video actually draws (supersampling = clean edges, small files)
#   2) a mask from an anime-character segmentation model (rembg "isnet-anime"), combined later with the green key
# in : /content/in/<name>.mp4      out: /content/out/<name>_rgb.mp4 (yuv444, crf 10) + <name>_a.mp4 (segmentation mask)
import glob, os, subprocess, sys, time
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
def sh(c):
    print("$", c[:200], flush=True); t = time.time()
    subprocess.run("set -o pipefail; " + c, shell=True, check=True, executable="/bin/bash"); print(f"  ({time.time()-t:.0f}s)", flush=True)
sh('pip install -q spandrel "rembg[gpu]" onnxruntime-gpu 2>&1 | tail -2 || true')
W = "/content/models"; os.makedirs(W, exist_ok=True)
pth = f"{W}/realesr-animevideov3.pth"
for url in ["https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth"]:
    if not os.path.exists(pth): subprocess.run(f"wget -q -O {pth} '{url}' || rm -f {pth}", shell=True)
print("weights:", os.path.exists(pth) and os.path.getsize(pth), flush=True)
import numpy as np, torch
from PIL import Image
from spandrel import ModelLoader
sr = ModelLoader().load_from_file(pth).cuda().eval().half()
from rembg import new_session, remove
seg = new_session("isnet-anime")
print("rembg providers:", getattr(seg, "inner_session", None) and seg.inner_session.get_providers(), flush=True)
os.makedirs("/content/out", exist_ok=True)
WIDTH = {"intro_lc": int(os.environ.get("INTRO_W", "1008")), "verdict_lc": int(os.environ.get("VERDICT_W", "1008"))}; DEFAULT_W = int(os.environ.get("MINI_W", "560"))  # drawn sizes in the 1080 video
SEG = set(os.environ.get("SEG_CLIPS", "intro_lc,verdict_lc").split(","))   # segmentation is slow: only for the big presenter clips
def enc(path, w, h, fps, fmt):
    return subprocess.Popen(["ffmpeg","-v","error","-y","-f","rawvideo","-pix_fmt",fmt,"-s",f"{w}x{h}","-r",fps,"-i","-",
                             "-c:v","libx264","-crf","12","-preset","medium","-pix_fmt","yuv444p",path], stdin=subprocess.PIPE)
clips = sorted(glob.glob("/content/in/*.mp4")) + sorted(glob.glob("/content/in2_*.mp4"))
order = {"intro_lc": 0, "verdict_lc": 1}
clips.sort(key=lambda c: order.get(os.path.basename(c)[:-4].replace("in2_", ""), 9))
for clip in clips:
    name = os.path.basename(clip)[:-4].replace("in2_", "")
    if os.path.exists(f"/content/out/{name}_rgb.mp4"): continue
    fps = subprocess.run(["ffprobe","-v","error","-select_streams","v","-show_entries","stream=r_frame_rate","-of","csv=p=0",clip],capture_output=True,text=True).stdout.strip()
    w0, h0 = [int(v) for v in subprocess.run(["ffprobe","-v","error","-select_streams","v","-show_entries","stream=width,height","-of","csv=p=0",clip],capture_output=True,text=True).stdout.strip().split(",")]
    dec = subprocess.Popen(["ffmpeg","-v","error","-i",clip,"-f","rawvideo","-pix_fmt","rgb24","-"], stdout=subprocess.PIPE)
    tw = WIDTH.get(name, DEFAULT_W); th = round(h0 * tw / w0 / 2) * 2
    erg = enc(f"/content/out/{name}_rgb.mp4", tw, th, fps, "rgb24")
    ea = enc(f"/content/out/{name}_a.mp4", tw, th, fps, "gray") if name in SEG else None
    i = 0; t = time.time()
    while True:
        b = dec.stdout.read(w0*h0*3)
        if len(b) < w0*h0*3: break
        a = np.frombuffer(b, np.uint8).reshape(h0, w0, 3).copy()
        x = torch.from_numpy(a).cuda().permute(2, 0, 1)[None].half() / 255
        with torch.no_grad(): y = torch.nn.functional.interpolate(sr(x).float(), size=(th, tw), mode="area").clamp(0, 1)
        up = (y[0].permute(1, 2, 0).float().cpu().numpy() * 255 + 0.5).astype(np.uint8)
        erg.stdin.write(up.tobytes())
        if ea:  # mask from the original-size frame (the model works at 1024 anyway), then enlarged
            m = remove(Image.fromarray(a), session=seg, only_mask=True, post_process_mask=False).resize((tw, th), Image.LANCZOS)
            ea.stdin.write(np.asarray(m.convert("L")).tobytes())
        if i % 50 == 0: print(name, i, f"{time.time()-t:.0f}s", flush=True)
        i += 1
    erg.stdin.close(); erg.wait()
    if ea: ea.stdin.close(); ea.wait()
    print("done", name, i, f"{time.time()-t:.0f}s", flush=True)
sh("ls -la /content/out")
