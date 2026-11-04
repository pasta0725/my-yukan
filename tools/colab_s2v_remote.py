# Runs INSIDE a Colab GPU runtime (sent by `colab exec -f`).
# Makes the character speak the given audio with Wan2.2-S2V-14B: /content/in/{base_green.png,intro.wav,verdict.wav} -> /content/out/*.mp4
import glob, os, re, subprocess, time
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
def sh(c):
    print("$", c, flush=True); t = time.time()
    subprocess.run("set -o pipefail; " + c, shell=True, check=True, executable="/bin/bash"); print(f"  ({time.time()-t:.0f}s)", flush=True)
sh("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader; df -h /content | tail -1")
sh('python -c "import torch,sys;print(sys.version.split()[0], torch.__version__, torch.version.cuda)"')
os.chdir("/content")
if not os.path.exists("Wan2.2"):
    sh("git clone -q --depth 1 https://github.com/Wan-Video/Wan2.2")
    # no flash-attn on Colab: fall back to PyTorch attention
    p = "Wan2.2/wan/modules/attention.py"
    open(p, "a").write('''
if not (FLASH_ATTN_2_AVAILABLE or FLASH_ATTN_3_AVAILABLE):
    def flash_attention(q, k, v, q_lens=None, k_lens=None, dropout_p=0., softmax_scale=None, q_scale=None,
                        causal=False, window_size=(-1, -1), deterministic=False, dtype=torch.bfloat16, version=None):
        return attention(q, k, v, dropout_p=dropout_p, causal=causal, dtype=dtype)
''')
    p = "Wan2.2/wan/__init__.py"; s = open(p).read()
    s = s.replace("from .animate import WanAnimate", "try:\n    from .animate import WanAnimate\nexcept Exception as e:\n    print('animate skipped:', e)")
    open(p, "w").write(s)
sh('pip install -q "transformers>=4.49.0,<=4.51.3" "diffusers>=0.31.0" easydict ftfy dashscope imageio-ffmpeg decord librosa einops hf_transfer 2>&1 | tail -3')
if not os.path.exists("/content/S2V/config.json"):
    sh("HF_HUB_ENABLE_HF_TRANSFER=1 python -c \"from huggingface_hub import snapshot_download as s; s('Wan-AI/Wan2.2-S2V-14B', local_dir='/content/S2V', max_workers=16)\"")
os.makedirs("/content/out", exist_ok=True)
PROMPT = ("An anime girl with blue hair, a white lab coat and goggles on her head talks cheerfully to the camera like a news presenter, "
          "with natural head movement, blinking and small hand gestures. Plain solid green background. Anime illustration style, clean lines.")
for n in ["intro", "verdict"]:
    if not os.path.exists(f"/content/in/{n}.wav"): continue
    sh(f'cd Wan2.2 && python generate.py --task s2v-14B --size 720*1280 --ckpt_dir /content/S2V --offload_model False --convert_model_dtype '
       f'--prompt "{PROMPT}" --image /content/in/base_green.png --audio /content/in/{n}.wav --save_file /content/out/{n}.mp4 --base_seed 7 2>&1 | grep -vE "it/s\\]|s/it\\]" | tail -40')
sh("ls -la /content/out")
