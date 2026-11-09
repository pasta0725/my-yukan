"""Automatic voice check for a finished Short (2026-11-10, for the auto shorts: nobody listens before it goes out).
Transcribes the video's audio with Whisper and compares it, as hiragana, with what the script says should be read.
Finds: misreadings (8日間 read as ようとうかん), leftover pieces of other lines (split_tts mistakes), missing lines.

  python3 tools/check_voice.py <video.mp4 or audio> <spec.json> [--out report.json]
spec.json = the short's spec (lines[].say). Runs on GitHub Actions (.github/workflows/voice-check.yml).
Exit code 0 = looks fine, 2 = something to look at (see the report). Numbers/English written differently
in the transcript can show up as small differences; the report gives the context so a person/agent can judge."""
import json, re, sys, difflib, argparse, subprocess, os

ap = argparse.ArgumentParser(); ap.add_argument("media"); ap.add_argument("spec"); ap.add_argument("--out", default="voice_report.json")
ap.add_argument("--model", default="large-v3-turbo")
a = ap.parse_args()

import pykakasi
kks = pykakasi.kakasi()
def kana(t):
    t = re.sub(r"\{SEC\}", "", t)
    h = "".join(x["hira"] for x in kks.convert(t))
    return re.sub(r"[\s、。,.!?！？「」『』（）()・…ー〜~\-:：]", "", h).lower()

wav = "/tmp/voice_check.wav"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", a.media, "-ac", "1", "-ar", "16000", wav], check=True)
from faster_whisper import WhisperModel
m = WhisperModel(a.model, device="cpu", compute_type="int8")
import wave, numpy as np   # pass samples, not the path (PyAV 15 broke faster-whisper's own file reading)
with wave.open(wav) as w: audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
segs, _ = m.transcribe(audio, language="ja", beam_size=5, vad_filter=False, condition_on_previous_text=False)
segs = list(segs)
heard_txt = "".join(s.text for s in segs)

spec = json.load(open(a.spec, encoding="utf-8"))
lines = [l for l in spec["lines"] if l.get("say")]
want = [(i, kana(l["say"])) for i, l in enumerate(lines)]
W = "".join(k for _, k in want); H = kana(heard_txt)
owner = []  # which script line each char of W belongs to
for i, k in want: owner += [i] * len(k)

sm = difflib.SequenceMatcher(None, W, H, autojunk=False)
issues = []
for op, i1, i2, j1, j2 in sm.get_opcodes():
    if op == "equal": continue
    li = owner[min(i1, len(owner) - 1)] if owner else -1
    issues.append({"kind": {"replace": "読みが違う", "delete": "読まれていない", "insert": "台本にない声"}[op],
                   "line": li + 1, "say": lines[li]["say"] if li >= 0 else "",
                   "expected": W[i1:i2], "heard": H[j1:j2], "context_heard": H[max(0, j1 - 8):j2 + 8]})
big = [x for x in issues if max(len(x["expected"]), len(x["heard"])) >= 3]
rep = {"similarity": round(sm.ratio(), 3), "issues_3plus": big, "issues_all": len(issues), "heard": heard_txt,
       "segments": [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text} for s in segs]}
json.dump(rep, open(a.out, "w"), ensure_ascii=False, indent=1)
print("similarity", rep["similarity"], "| differences of 3+ characters:", len(big))
for x in big: print(f'  line {x["line"]} {x["kind"]}: expected「{x["expected"]}」 heard「{x["heard"]}」  …{x["context_heard"]}…')
sys.exit(0 if rep["similarity"] >= 0.9 and len(big) <= 2 else 2)
