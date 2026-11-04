"""Ask the public Wan2.2-S2V demo to animate a still image so it speaks the given audio.
usage: python tools/s2v_run.py <image> <audio> <out.mp4> [480P|720P]"""
import shutil, sys, time
from gradio_client import Client, handle_file
img, aud, out = sys.argv[1:4]; res = sys.argv[4] if len(sys.argv) > 4 else "720P"
for attempt in range(3):
    try:
        c = Client("https://wan-ai-wan2-2-s2v.hf.space/", verbose=False)
        r = c.predict(handle_file(img), handle_file(aud), res, api_name="/predict")
        p = r["video"] if isinstance(r, dict) else r
        shutil.copy(p, out); print("saved", out); break
    except Exception as e:
        print("try", attempt, "failed:", repr(e)[:500], flush=True); time.sleep(30)
