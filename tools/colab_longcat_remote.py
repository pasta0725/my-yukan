# Runs INSIDE a Colab GPU runtime. Makes the character speak with LongCat-Video-Avatar 1.5 (8-step distilled).
# in: /content/in/{base_green.png,intro.wav,verdict.wav}   out: /content/out/<name>/*.mp4
import json, os, subprocess, time
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
def sh(c):
    print("$", c[:300], flush=True); t = time.time()
    subprocess.run("set -o pipefail; " + c, shell=True, check=True, executable="/bin/bash"); print(f"  ({time.time()-t:.0f}s)", flush=True)
sh("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader")
os.chdir("/content")
# no flash-attn wheel for this Python/PyTorch: a tiny stand-in built on PyTorch's own attention
os.makedirs("/content/shim/flash_attn", exist_ok=True)
open("/content/shim/flash_attn/__init__.py", "w").write('''
import torch, torch.nn.functional as F
def flash_attn_func(q, k, v, dropout_p=0.0, softmax_scale=None, causal=False, **kw):
    o = F.scaled_dot_product_attention(q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2), dropout_p=dropout_p, is_causal=causal, scale=softmax_scale)
    return o.transpose(1, 2)
def flash_attn_varlen_func(q, k, v, cu_seqlens_q, cu_seqlens_k, max_seqlen_q=None, max_seqlen_k=None, dropout_p=0.0, softmax_scale=None, causal=False, **kw):
    cq, ck, outs = cu_seqlens_q.tolist(), cu_seqlens_k.tolist(), []
    for i in range(len(cq) - 1):
        qi = q[cq[i]:cq[i+1]].transpose(0, 1)[None]; ki = k[ck[i]:ck[i+1]].transpose(0, 1)[None]; vi = v[ck[i]:ck[i+1]].transpose(0, 1)[None]
        outs.append(F.scaled_dot_product_attention(qi, ki, vi, scale=softmax_scale, is_causal=causal)[0].transpose(0, 1))
    return torch.cat(outs, 0)
''')
if not os.path.exists("LongCat-Video"):
    sh("git clone -q --depth 1 https://github.com/meituan-longcat/LongCat-Video")
sh('pip install -q "transformers==4.51.3" "diffusers==0.35.1" loguru ftfy av librosa soundfile pyloudnorm audio-separator einops imageio imageio-ffmpeg hf_transfer onnxruntime 2>&1 | grep -v "dependency conflicts\\|requires\\|^ERROR: pip" | tail -3 || true')
# 40 GB cards (A100): keep the 11 GB text encoder on the CPU (it runs once per clip) and park the KV cache in RAM
_vram = int(subprocess.run("nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits", shell=True, capture_output=True, text=True).stdout.split()[0] or 0)
LOW = os.environ.get("LOWVRAM") == "1" or _vram < 70000   # A100 40GB / L4: int8 DiT (official --use_int8) + text encoder on the CPU
print("GPU memory MB", _vram, "low-memory mode" if LOW else "", flush=True)
if LOW:
    d = "LongCat-Video/run_demo_avatar_single_audio_to_video.py"; t = open(d).read()
    if "LOWVRAM" not in t:
        t = t.replace("    pipe.to(local_rank)\n",
            "    dit.to(local_rank); vae.to(local_rank)  # LOWVRAM: text encoder stays on the CPU\n"
            "    _dev = torch.device(f'cuda:{local_rank}')\n"
            "    type(pipe)._execution_device = property(lambda self: _dev); type(pipe).device = property(lambda self: _dev)\n", 1)
        t = t.replace("offload_kv_cache=False", "offload_kv_cache=True"); open(d, "w").write(t)
    d = "LongCat-Video/longcat_video/pipeline_longcat_video_avatar.py"; t = open(d).read()
    t = t.replace("self.text_encoder(text_input_ids.to(device), mask.to(device)).last_hidden_state",
                  "self.text_encoder(text_input_ids.to(self.text_encoder.device), mask.to(self.text_encoder.device)).last_hidden_state.to(device)")
    open(d, "w").write(t)
W = "/content/w"
if not os.path.exists(f"{W}/LongCat-Video-Avatar-1.5/lora/dmd_lora.safetensors") or (LOW and not os.path.exists(f"{W}/LongCat-Video-Avatar-1.5/base_model_int8")):
    sh(f"""HF_HUB_ENABLE_HF_TRANSFER=1 python -c "
from huggingface_hub import snapshot_download as s
s('meituan-longcat/LongCat-Video-Avatar-1.5', local_dir='{W}/LongCat-Video-Avatar-1.5', max_workers=16,
  allow_patterns=['*.json','{'base_model_int8' if LOW else 'base_model'}/*','lora/*','scheduler/*','vocal_separator/*','whisper-large-v3/model.safetensors','whisper-large-v3/*.json','whisper-large-v3/*.txt'])
s('meituan-longcat/LongCat-Video', local_dir='{W}/LongCat-Video', max_workers=16, allow_patterns=['*.json','tokenizer/*','text_encoder/*','vae/*','scheduler/*'])
" """)
sh(f"du -sh {W}/*")
PROMPT = ("A cheerful anime girl with short dark blue hair with bright blue tips, blue eyes, round glasses-like goggles resting on her head, "
          "and computer-chip hair clips, wearing a white lab coat over a navy hoodie, stands facing the camera and talks like an energetic news presenter. "
          "She speaks with lively facial expressions, natural head movement, blinking and small hand gestures. Plain solid green background. "
          "Clean 2D anime illustration style, consistent character design.")
if os.path.exists("/content/in/prompt.txt"): PROMPT = open("/content/in/prompt.txt").read().strip()  # per-character description
jobs = json.load(open("/content/in/jobs.json")) if os.path.exists("/content/in/jobs.json") else [("intro", 1), ("verdict", 2)]  # [[name, segments, res?, image?, extra_prompt?], ...]
for job in jobs:
    name, seg = job[0], job[1]; res = job[2] if len(job) > 2 else "720p"  # 480p is enough for the small presenter
    img = job[3] if len(job) > 3 and job[3] else "base_green.png"  # e.g. the intro uses rina_fingers_4.png (hand showing the seconds)
    extra = job[4] if len(job) > 4 else ""  # added to the prompt for this clip only
    if not os.path.exists(f"/content/in/{name}.wav"): continue
    js = f"/content/in/{name}.json"
    json.dump({"prompt": (PROMPT + " " + extra).strip(), "cond_image": f"/content/in/{img}", "cond_audio": {"person1": f"/content/in/{name}.wav"}}, open(js, "w"))
    sh(f"cd LongCat-Video && PYTHONPATH=/content/shim torchrun --nproc_per_node=1 run_demo_avatar_single_audio_to_video.py "
       f"--context_parallel_size=1 --checkpoint_dir={W}/LongCat-Video-Avatar-1.5 --stage_1=ai2v --input_json={js} "
       f"--use_distill --model_type avatar-v1.5 {'--use_int8 ' if LOW else ''}--resolution {res} --num_segments {seg} --output_dir /content/out/{name} "
       f"2>&1 | grep -vE 'it/s\\]|s/it\\]' | tail -150")  # long tail: the real error of the child process sits above torchrun's own traceback
sh("ls -laR /content/out")
