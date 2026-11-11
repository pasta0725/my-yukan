"""Ask the same questions to Gemini (API) and record the real answers - for the 「比べてみた」 videos (2026-11-12).
ChatGPT is asked by the workflow (.github/workflows/ai-ask.yml) through Codex; Claude by the session itself.
  python3 tools/ai_ask.py gemini <questions.json> <out.json>
questions.json: {"name": "...", "questions": [{"id": "q1", "prompt": "..."}]}
Never prints the key."""
import json, os, re, sys, time, urllib.request, urllib.error, datetime

KEY = os.environ.get("GEMINI_API_KEY", "")
API = "https://generativelanguage.googleapis.com/v1beta"


def models():
    req = urllib.request.Request(f"{API}/models?pageSize=200", headers={"x-goog-api-key": KEY})
    return [m["name"].split("/")[-1] for m in json.load(urllib.request.urlopen(req, timeout=60)).get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])]


def picks(names):
    """newest pro, then newest flash: the free tier often has no quota for pro (429), then flash answers"""
    ok = [n for n in names if re.match(r"gemini-\d", n) and not re.search(r"tts|image|live|audio|lite|exp|embed|robotics|computer", n)]
    ver = lambda n: [float(x) for x in re.findall(r"\d+(?:\.\d+)?", n)[:1]] or [0]
    out = []
    for kind in ("pro", "flash"):
        c = sorted([n for n in ok if kind in n], key=lambda n: (ver(n), "preview" not in n), reverse=True)
        if c: out.append(c[0])
    return out or ["gemini-flash-latest"]


def pick(names):
    """the newest general model: pro first, then flash (no tts/image/live/lite/exp/embedding variants)"""
    ok = [n for n in names if re.match(r"gemini-\d", n) and not re.search(r"tts|image|live|audio|lite|exp|embed|preview-tts|robotics|computer", n)]
    ver = lambda n: [float(x) for x in re.findall(r"\d+(?:\.\d+)?", n)[:1]] or [0]
    for kind in ("pro", "flash"):
        c = sorted([n for n in ok if kind in n], key=lambda n: (ver(n), "preview" not in n), reverse=True)
        if c: return c[0]
    return "gemini-flash-latest"


def ask(model, prompt):
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    req = urllib.request.Request(f"{API}/models/{model}:generateContent", data=json.dumps(body).encode(),
                                 headers={"x-goog-api-key": KEY, "Content-Type": "application/json"})
    for a in range(3):
        try:
            r = json.load(urllib.request.urlopen(req, timeout=600)); break
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 503) or a == 2: raise
            time.sleep(20 * (a + 1))
        except (TimeoutError, urllib.error.URLError):   # a thinking model can take long; try again
            if a == 2: raise
            time.sleep(10)
    return "".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"] if not p.get("thought"))


if __name__ == "__main__":
    q = json.load(open(sys.argv[2], encoding="utf-8"))
    for m in picks(models()):
        try:
            out = {"ai": "Gemini", "model": m, "answers": []}
            for x in q["questions"]:
                out["answers"].append({"id": x["id"], "asked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                                       "answer": ask(m, x["prompt"]).strip()})
            break
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            print("model", m, "failed", getattr(e, "code", type(e).__name__), "- trying the next one")
    json.dump(out, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("gemini", m, len(out["answers"]))
