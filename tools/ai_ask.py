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
    rest = sorted([n for n in ok if n not in out and ("pro" in n or "flash" in n)], key=lambda n: (ver(n), "pro" in n, "preview" not in n), reverse=True)
    return out + ["gemini-flash-latest"] + rest   # when the newest ones are busy, older general models still answer


def pick(names):
    """the newest general model: pro first, then flash (no tts/image/live/lite/exp/embedding variants)"""
    ok = [n for n in names if re.match(r"gemini-\d", n) and not re.search(r"tts|image|live|audio|lite|exp|embed|preview-tts|robotics|computer", n)]
    ver = lambda n: [float(x) for x in re.findall(r"\d+(?:\.\d+)?", n)[:1]] or [0]
    for kind in ("pro", "flash"):
        c = sorted([n for n in ok if kind in n], key=lambda n: (ver(n), "preview" not in n), reverse=True)
        if c: return c[0]
    return "gemini-flash-latest"


def ask(model, prompt):
    """streamed (server-sent events), so a long think does not look like a dead connection; prints how long it took"""
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    req = urllib.request.Request(f"{API}/models/{model}:streamGenerateContent?alt=sse", data=json.dumps(body).encode(),
                                 headers={"x-goog-api-key": KEY, "Content-Type": "application/json"})
    for a in range(3):
        t0 = time.time(); txt = []
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                for raw in r:
                    line = raw.decode("utf-8", "replace").strip()
                    if not line.startswith("data:"): continue
                    d = json.loads(line[5:])
                    for c in d.get("candidates", []):
                        txt += [p.get("text", "") for p in c.get("content", {}).get("parts", []) if not p.get("thought")]
            print(" ", model, f"{time.time() - t0:.0f}s", flush=True)
            return "".join(txt)
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 503) or a == 2: raise
            time.sleep(20 * (a + 1))
        except (TimeoutError, urllib.error.URLError):
            print(" ", model, "timeout", f"{time.time() - t0:.0f}s", flush=True)
            if a >= 1: raise   # one retry, then the next model


if __name__ == "__main__":
    q = json.load(open(sys.argv[2], encoding="utf-8"))
    names = models(); print("models:", " ".join(n for n in names if n.startswith("gemini-")), flush=True)
    for m in picks(names)[:8]:
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
