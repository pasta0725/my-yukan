"""Assemble the timing plan and the final audio for a news Short.
usage: python3 tools/short_plan.py <spec.json> <work_dir>
spec.json: {"wav_dir": "...", "lines": [{"say": "...", "show": "...", "scene": "hook", "puppet": false, "se": "don"}, ...],
            "speed": 1.12, "gap": 0.03, "pause_max": 0.05, "tail_logo": 2.0, "sfx_dir": "...", "lipsync": "path/to/python-with-pyopenjtalk"}
pause_max: every pause inside a line (at 、 and between phrases) is shortened to at most this many seconds,
           and gap is the silence between lines -> the "no breath" delivery the user asked for (2026-11-07, like 岡野タケシ)
writes <work_dir>/plan.js (window.PLAN) and <work_dir>/audio.wav"""
import json, os, re, subprocess, sys, wave
import numpy as np

spec = json.load(open(sys.argv[1], encoding="utf-8")); W = sys.argv[2]; os.makedirs(W, exist_ok=True)
SR = 48000; FPS = 30
speed, gap, tail = spec.get("speed", 1.12), spec.get("gap", 0.03), spec.get("tail_logo", 2.0)
pause_max = spec.get("pause_max", 0.05)


def run(*a): subprocess.run(a, check=True)


def readw(p):
    w = wave.open(p); x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    if w.getnchannels() == 2: x = x.reshape(-1, 2).mean(axis=1)
    return x, w.getframerate()


def squeeze(x, pmax, thr_db=-40, win=0.01):
    """shorten every quiet run longer than pmax seconds to pmax; returns (new signal, kept [(start,end)] in samples)"""
    if pmax is None: return x, [(0, len(x))]
    h = int(SR * win); n = len(x) // h
    if n == 0: return x, [(0, len(x))]
    rms = np.sqrt((x[: n * h].reshape(n, h) ** 2).mean(axis=1) + 1e-12)
    quiet = 20 * np.log10(rms) < thr_db
    keep, i, k = [], 0, int(pmax / win)
    while i < n:
        j = i
        while j < n and quiet[j] == quiet[i]: j += 1
        if quiet[i] and (j - i) > k:
            m = (i + j) // 2; keep.append((m - k // 2, m - k // 2 + k))   # keep pmax of silence from the middle
        else: keep.append((i, j))
        i = j
    kept = [(a * h, b * h) for a, b in keep]; kept[-1] = (kept[-1][0], len(x))
    return np.concatenate([x[a:b] for a, b in kept]), kept


def writew(p, x, sr=SR, ch=1):
    x = np.clip(x, -1, 1)
    with wave.open(p, "wb") as w:
        w.setnchannels(ch); w.setsampwidth(2); w.setframerate(sr); w.writeframes((x * 32767).astype(np.int16).tobytes())


# 1) each line: cut silence at both ends, speed up, resample to 48 kHz
segs = []
for i, ln in enumerate(spec["lines"], 1):
    src = os.path.join(spec["wav_dir"], f"s{i}.wav"); dst = os.path.join(W, f"l{i}.wav")
    run("ffmpeg", "-v", "error", "-y", "-i", src, "-af",
        f"silenceremove=start_periods=1:start_threshold=-42dB:start_silence=0.02,areverse,"
        f"silenceremove=start_periods=1:start_threshold=-42dB:start_silence=0.05,areverse,atempo={speed},aresample={SR}",
        "-ac", "1", dst)
    x, _ = readw(dst)
    x, _ = squeeze(x, pause_max); writew(dst, x); segs.append(x)

# 2) timeline
t = 0.25; lines = []
for i, (ln, x) in enumerate(zip(spec["lines"], segs)):
    d = len(x) / SR; lines.append({**ln, "start": round(t, 3), "end": round(t + d, 3)}); t += d + gap
voice_end = t - gap; T = voice_end + 0.35 + tail

# 3) telop chunks: split the shown text into 5-15 character pieces, timed by length
def chunks(s):
    parts = [p for p in re.split(r"(?<=[、。！？])", s) if p.strip()]
    out = []
    for p in parts:
        p = p.strip()
        while len(p) > 15:
            cut = max([m.end() for m in re.finditer(r"[をにはがでとのもへ]", p[:15])] or [12])
            out.append(p[:cut]); p = p[cut:]
        if p:
            if len(p) <= 3 and out and len(out[-1]) + len(p) <= 18: out[-1] += p  # no tiny leftovers
            else: out.append(p)
    return out
tel = []
for ln in lines:
    cs = chunks(ln["show"]); w = [max(3, len(re.sub(r"[、。]", "", c))) for c in cs]; tot = sum(w); s = ln["start"]
    for c, k in zip(cs, w):
        d = (ln["end"] - ln["start"]) * k / tot
        tel.append({"start": round(s, 3), "end": round(s + d, 3), "text": re.sub(r"[、。]$", "", c)}); s += d

# 4) lip sync for the lines where the presenter is on screen
voices = {}
for i, ln in enumerate(lines):
    if ln.get("puppet"):
        js = os.path.join(W, f"lip{i}.js")
        run(spec["lipsync"], "-I", os.path.join(os.path.dirname(__file__), "lipsync_ja.py"), ln["say"], os.path.join(W, f"l{i+1}.wav"), js, str(FPS))
        txt = open(js, encoding="utf-8").read(); voices[i] = json.loads(txt[txt.index("=") + 1:].rstrip(";\n "))

# 5) audio: narration + quiet music + effects, music stops with the voice (logo is silent)
n = int(T * SR); nar = np.zeros(n); se = np.zeros(n)
for ln, x in zip(lines, segs):
    s = int(ln["start"] * SR); nar[s:s + len(x)] += x[: max(0, n - s)]
def add_se(name, at, vol=1.0):
    p = os.path.join(spec["sfx_dir"], f"se_{name}.wav")
    if not os.path.exists(p): return
    x, _ = readw(p); s = int(at * SR); se[s:s + len(x)] += vol * x[: max(0, n - s)]
for ln in lines:
    if ln.get("se"): add_se(ln["se"], max(0, ln["start"] - 0.06), ln.get("se_vol", 0.8))
    add_se("whoosh", max(0, ln["start"] - 0.18), 0.35)
bgm, _ = readw(os.path.join(spec["sfx_dir"], "bgm.wav"))
music = np.zeros(n); m = min(len(bgm), n); music[:m] = bgm[:m] * 0.16
stop = int((voice_end + 0.3) * SR); fade = int(0.25 * SR)
music[stop - fade:stop] *= np.linspace(1, 0, fade); music[stop:] = 0
# duck the music a little while she speaks
envv = np.convolve(np.abs(nar), np.ones(2400) / 2400, mode="same"); music *= 1 - 0.35 * np.clip(envv * 12, 0, 1)
mix = nar * 0.95 + music + se * 0.6
writew(os.path.join(W, "audio.wav"), mix / max(1.0, np.abs(mix).max() / 0.98))
plan = {"T": round(T, 3), "fps": FPS, "voice_end": round(voice_end, 3), "lines": lines, "tel": tel, "voices": voices}
open(os.path.join(W, "plan.js"), "w", encoding="utf-8").write("window.PLAN=" + json.dumps(plan, ensure_ascii=False) + ";")
print(json.dumps({"T": plan["T"], "lines": [(l["scene"], l["start"], l["end"]) for l in lines], "telops": len(tel)}, ensure_ascii=False))
