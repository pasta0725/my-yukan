"""Assemble the timing plan and the final audio for a news Short.
usage: python3 tools/short_plan.py <spec.json> <work_dir>
spec.json: {"wav_dir": "...", "lines": [{"say": "...", "show": "...", "scene": "hook", "puppet": false, "se": "don"}, ...],
            "speed": 1.15, "gap": 0.03, "period_pause": 0.04, "comma_max": 0.30, "tail_logo": 2.0, "sfx_dir": "...", "lipsync": "path/to/python-with-pyopenjtalk"}
period_pause / comma_max: the pause at 「。」 inside a line is cut to period_pause (no breath, like 岡野タケシ),
           the pause at 「、」 may stay up to comma_max; short silences such as the small 「っ」 are left alone (user, 2026-11-07).
           gap is the silence between lines (each line ends with 「。」, so it is short too)
writes <work_dir>/plan.js (window.PLAN) and <work_dir>/audio.wav
intro line: write "say": "このニュース、{SEC}でまとめます。" ({SEC} becomes 「40秒」 or 「1分」, max 60) and put the number used for its TTS in spec "sec" (see step 2b)."""
import json, os, re, subprocess, sys, wave
import numpy as np

spec = json.load(open(sys.argv[1], encoding="utf-8")); W = sys.argv[2]; os.makedirs(W, exist_ok=True)
SR = 48000; FPS = 30
speed, gap, tail = spec.get("speed", 1.12), spec.get("gap", 0.03), spec.get("tail_logo", 2.0)
period_pause, comma_max = spec.get("period_pause", 0.04), spec.get("comma_max", 0.30)


def run(*a): subprocess.run(a, check=True)


def readw(p):
    w = wave.open(p); x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    if w.getnchannels() == 2: x = x.reshape(-1, 2).mean(axis=1)
    return x, w.getframerate()


def squeeze(x, say, period=0.04, comma_max=0.30, min_pause=0.14, thr_db=-40, win=0.01):
    """no breath at 「。」: the pause at each sentence end inside the line is cut to `period` seconds.
    「、」 may keep a breath (capped at comma_max). Short silences (< min_pause), such as the small 「っ」, are never touched.
    Which pause belongs to which 「。」 is found by position: each 。 takes the nearest long pause to where it falls in the text."""
    h = int(SR * win); n = len(x) // h
    if n == 0: return x
    quiet = 20 * np.log10(np.sqrt((x[: n * h].reshape(n, h) ** 2).mean(axis=1) + 1e-12)) < thr_db
    runs, i = [], 0
    while i < n:
        j = i
        while j < n and quiet[j] == quiet[i]: j += 1
        if quiet[i] and i > 0 and j < n and (j - i) * win >= min_pause: runs.append([i, j, "comma"])
        i = j
    body = say.rstrip("。！？ 　")
    chars = [c for c in body if c not in "、。！？「」 　"]; tot = max(1, len(chars))
    k = 0
    for c in body:
        if c in "。！？" and runs:
            frac = k / tot; want = frac * n
            free = [r for r in runs if r[2] == "comma"]
            if free: min(free, key=lambda r: abs((r[0] + r[1]) / 2 - want))[2] = "period"
        elif c not in "、「」 　": k += 1
    out, pos = [], 0
    for a, b, kind in runs:
        keep = int((period if kind == "period" else min(comma_max, (b - a) * win)) / win)
        k0 = (a + b) // 2 - keep // 2                      # keep `keep` windows in the middle of the pause, cut the rest
        out.append(x[pos * h: a * h]); out.append(x[k0 * h: (k0 + keep) * h]); pos = b
    out.append(x[pos * h:])
    return np.concatenate(out)


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
    x = squeeze(x, ln["say"], period_pause, comma_max); writew(dst, x); segs.append(x)

# 2) timeline
t = 0.25; lines = []
for i, (ln, x) in enumerate(zip(spec["lines"], segs)):
    d = len(x) / SR; lines.append({**ln, "start": round(t, 3), "end": round(t + d, 3)}); t += d + gap
voice_end = t - gap; T = voice_end + 0.35 + tail

# 2b) 「このニュース、{SEC}でまとめます」: SEC = the talk AFTER that line (logo not counted), rounded UP to 10 s, at most 60.
#     40 -> 「40秒」, 60 -> 「1分」 (user rule 2026-11-08). Over 60 s: exit 4, the script must be made shorter.
#     The line's audio must say the same number: spec "sec" = the number used for that line's TTS.
#     If it differs, exit 3 with the right number -> make that one line again with it, then run this again.
#     plan "fingers" = how many fingers rina shows in the intro (10-50 s -> 1-5, 1分 -> 1). Old specs that write "{SEC}秒" still work.
import math
def sec_word(s): return "1分" if s == 60 else f"{s}秒"
for ln in lines:
    if "{SEC}" in ln.get("say", "") or "{SEC}" in ln.get("show", ""):
        after = voice_end - ln["end"]
        sec = max(10, math.ceil(after / 10 - 1e-9) * 10)
        if sec > 60:
            print(json.dumps({"too_long": round(after, 1), "max": 60, "cut": round(after - 60, 1)}, ensure_ascii=False)); sys.exit(4)
        if spec.get("sec") != sec:
            print(json.dumps({"need_sec": sec, "line": ln["say"].replace("{SEC}秒", "{SEC}").replace("{SEC}", sec_word(sec))}, ensure_ascii=False)); sys.exit(3)
        for k in ("say", "show"): ln[k] = ln.get(k, "").replace("{SEC}秒", "{SEC}").replace("{SEC}", sec_word(sec))
        spec["fingers"] = 1 if sec == 60 else sec // 10

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
# pose_at: when rina must be in the finger pose = when she starts saying the number after 「このニュース、」
#          (end of the comma pause in the intro line). The page moves her into the pose just before it (puppet.js).
pose_at = None
for ln, x in zip(lines, segs):
    if ln.get("scene") == "intro":
        h = int(SR * 0.01); n2 = len(x) // h
        q = 20 * np.log10(np.sqrt((x[: n2 * h].reshape(n2, h) ** 2).mean(axis=1) + 1e-12)) < -40
        best, i = None, 0
        while i < n2:
            j = i
            while j < n2 and q[j] == q[i]: j += 1
            if q[i] and 0.15 * n2 < i < 0.85 * n2 and (best is None or j - i > best[1] - best[0]): best = (i, j)
            i = j
        pose_at = round(ln["start"] + (best[1] if best else n2 * 0.45) * 0.01, 3)
plan = {"T": round(T, 3), "fps": FPS, "voice_end": round(voice_end, 3), "lines": lines, "tel": tel, "voices": voices, "fingers": spec.get("fingers"), "pose_at": pose_at}
open(os.path.join(W, "plan.js"), "w", encoding="utf-8").write("window.PLAN=" + json.dumps(plan, ensure_ascii=False) + ";")
print(json.dumps({"T": plan["T"], "fingers": plan["fingers"], "lines": [(l["scene"], l["start"], l["end"]) for l in lines], "telops": len(tel)}, ensure_ascii=False))
