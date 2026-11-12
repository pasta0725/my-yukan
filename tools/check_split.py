"""Check that split_tts.py cut each line in the right place, by transcribing every piece (2026-11-13, Issue #16).
A cut in the wrong place moves a few words into the next line; split_tts.py's CHECK (speed / short pause) can miss it.
usage: python3 tools/check_split.py <lines.json> <dir with s1.wav s2.wav ...>
needs: pip install faster-whisper   (model "small", about 1 minute for a Short on a CPU)
Prints each line's script and what was heard; LOOK lines are the ones to listen to. Exit 3 if any LOOK."""
import difflib, json, re, sys, wave
import numpy as np
from faster_whisper import WhisperModel

lines = [l for g in json.load(open(sys.argv[1], encoding="utf-8"))["lines"] for l in g.split("\n") if l.strip()]
m = WhisperModel("small", device="cpu", compute_type="int8")
norm = lambda s: re.sub(r"[\s、。，．,.!?！？「」『』（）()・…ー〜~]", "", s)


def load(p):
    w = wave.open(p); sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    return np.interp(np.arange(0, len(x), sr / 16000), np.arange(len(x)), x).astype(np.float32)


bad = 0
for i, l in enumerate(lines, 1):
    heard = "".join(s.text for s in m.transcribe(load(f"{sys.argv[2]}/s{i}.wav"), language="ja", beam_size=5)[0])
    a, b = norm(l), norm(heard)
    sim = difflib.SequenceMatcher(None, a, b).ratio()
    # words of the next / previous line showing up here = a cut in the wrong place
    nxt = norm(lines[i])[:6] if i < len(lines) else ""
    prv = norm(lines[i - 2])[-6:] if i > 1 else ""
    leak = (nxt and nxt[:4] in b[-12:]) or (prv and prv[-4:] in b[:12])
    look = bool(sim < 0.6 or len(b) > len(a) * 1.35 or leak)
    bad += look
    print(f"s{i} {'LOOK ' if look else ''}{sim:.2f}\n  script: {l}\n  heard : {heard}")
print("ok" if not bad else f"{bad} line(s) to listen to")
sys.exit(3 if bad else 0)
