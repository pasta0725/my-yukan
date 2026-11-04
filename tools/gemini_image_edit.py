"""Edit one base image many times with a Gemini image model (no key in this file).
usage: python3 -I tools/gemini_image_edit.py <jobs.json> <out_dir>
jobs.json: {"base": "path.png", "models": ["model-a", "model-b"], "jobs": [{"name": "no_bangs", "prompt": "..."}]}
Tries the models in order until one works, writes <out_dir>/<name>.png and <out_dir>/log.txt."""
import base64, json, os, sys, time, urllib.error, urllib.request

cfg = json.load(open(sys.argv[1], encoding="utf-8"))
out = sys.argv[2]
os.makedirs(out, exist_ok=True)
key = os.environ.get("GEMINI_API_KEY", "")
H = {"Content-Type": "application/json", "x-goog-api-key": key}
log = open(os.path.join(out, "log.txt"), "a", encoding="utf-8")


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    log.write(s + "\n"); log.flush()


# which image models can this key see?
try:
    req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200", headers=H)
    models = json.load(urllib.request.urlopen(req, timeout=60)).get("models", [])
    say("image models:", [m["name"] for m in models if "image" in m["name"]])
except Exception as e:  # noqa: BLE001
    say("list error", e)

img_b64 = base64.b64encode(open(cfg["base"], "rb").read()).decode()
COMMON = ("Change ONLY what is described. Keep everything else exactly identical to the input image: "
          "same canvas size, same character position and scale, same face, same pose, same colours, same background. "
          "Do not zoom, crop, shift or tilt anything.\n\n")


def edit(model, prompt):
    body = {"contents": [{"parts": [{"inline_data": {"mime_type": "image/png", "data": img_b64}},
                                    {"text": COMMON + prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]}}
    req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                                 data=json.dumps(body).encode(), headers=H)
    d = json.load(urllib.request.urlopen(req, timeout=300))
    for p in d["candidates"][0]["content"]["parts"]:
        if "inlineData" in p or "inline_data" in p:
            x = p.get("inlineData") or p.get("inline_data")
            return base64.b64decode(x["data"]), x.get("mimeType") or x.get("mime_type")
    raise RuntimeError("no image in reply: " + json.dumps(d)[:300])


model_ok = None
for job in cfg["jobs"]:
    for m in ([model_ok] if model_ok else cfg["models"]):
        try:
            data, mime = edit(m, job["prompt"])
            ext = "png" if "png" in (mime or "") else "jpg"
            open(os.path.join(out, f"{job['name']}.{ext}"), "wb").write(data)
            say("ok", job["name"], m, mime, len(data))
            model_ok = m
            break
        except urllib.error.HTTPError as e:
            say("fail", job["name"], m, e.code, e.read().decode(errors="replace")[:900].replace("\n", " "))
        except Exception as e:  # noqa: BLE001
            say("fail", job["name"], m, repr(e)[:300])
    time.sleep(12)
