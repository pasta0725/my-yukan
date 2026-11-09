# Runs INSIDE the Modal GPU container (tools/modal_avatar.py, model "echomimic"). EchoMimicV3-Flash (8 steps, 1.3B, Jan 2026).
# in: /content/in/{jobs.json, <image>, <name>.wav, prompt.txt?}   out: /content/out/<name>.mp4   weights: /content/w/em3
import glob, json, os, shutil, subprocess, time


def sh(c):
    print("$", c[:300], flush=True); t = time.time()
    subprocess.run("set -o pipefail; " + c, shell=True, check=True, executable="/bin/bash"); print(f"  ({time.time()-t:.0f}s)", flush=True)


sh("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader")
W = "/content/w/em3"
if not os.path.exists(f"{W}/flash/transformer/diffusion_pytorch_model.safetensors"):
    from huggingface_hub import snapshot_download as s, hf_hub_download as f
    s("alibaba-pai/Wan2.1-Fun-V1.1-1.3B-InP", local_dir=f"{W}/flash/Wan2.1-Fun-V1.1-1.3B-InP", max_workers=16)
    s("TencentGameMate/chinese-wav2vec2-base", local_dir=f"{W}/flash/chinese-wav2vec2-base", max_workers=16)
    p = f("BadToBest/EchoMimicV3", "echomimicv3-flash-pro/diffusion_pytorch_model.safetensors", local_dir=f"{W}/dl")
    os.makedirs(f"{W}/flash/transformer", exist_ok=True); shutil.move(p, f"{W}/flash/transformer/diffusion_pytorch_model.safetensors")
PROMPT = ("A 2D anime girl in clean cel-shaded anime illustration style talks like a lively news presenter, facing the camera, "
          "with natural mouth movement in sync with her speech, natural head movement and blinking. Plain solid green background.")
if os.path.exists("/content/in/prompt.txt"): PROMPT = open("/content/in/prompt.txt").read().strip()
for job in json.load(open("/content/in/jobs.json")):
    name = job[0]; img = job[3] if len(job) > 3 and job[3] else "base_green.png"; extra = job[4] if len(job) > 4 else ""
    if not os.path.exists(f"/content/in/{name}.wav"): continue
    o = f"/content/tmp_{name}"; shutil.rmtree(o, ignore_errors=True)
    sh(f"cd /opt/em3 && python infer_flash.py --image_path /content/in/{img} --audio_path /content/in/{name}.wav "
       f"--prompt {json.dumps((PROMPT + ' ' + extra).strip())} --num_inference_steps 8 --config_path config/config.yaml "
       f"--model_name {W}/flash/Wan2.1-Fun-V1.1-1.3B-InP --ckpt_idx 50000 --transformer_path {W}/flash/transformer/diffusion_pytorch_model.safetensors "
       f"--save_path {o} --wav2vec_model_dir {W}/flash/chinese-wav2vec2-base --sampler_name Flow_Unipc --video_length 250 "
       f"--guidance_scale 6.0 --audio_guidance_scale 3.0 --audio_scale 1.0 --neg_scale 1.0 --neg_steps 0 --seed 43 --enable_teacache "
       f"--teacache_threshold 0.1 --num_skip_start_steps 5 --riflex_k 6 --weight_dtype bfloat16 --sample_size 960 960 --fps 25 --shift 5.0 "
       f"2>&1 | grep -vE 'it/s\\]|s/it\\]' | tail -30")
    v = [p for p in glob.glob(f"{o}/*.mp4") if not p.endswith("_tmp.mp4")]
    if v: shutil.copy(v[0], f"/content/out/{name}.mp4")
sh("ls -la /content/out")
