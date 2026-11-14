"""Helpers for the automatic Short pipeline on GitHub Actions (short-voice.yml, short-build.yml, short-upload.yml), 2026-11-14.
The user's request: the fixed steps that Sonnet executors used to run by hand now run on GitHub Actions with no AI; the
parent (Opus) only dispatches, waits once and reads 「RESULT: OK|LOOK|FAILED」 and the 「- LOOK …」 lines (tools/auto_short.md 2-2).

  python3 tools/short_auto.py tts-count <name>
      Gemini TTS requests made today (JST) for this short (narration/<name> and narration/<name>_*), from the branch work.
  python3 tools/short_auto.py voice-report <name> <lines.json> <split.log> <check.log> <count> <out.md>
      report of split_tts.py + check_split.py.
  python3 tools/short_auto.py assemble <spec.json> <name> <out dir>
      picks the audio of every script line (newest narration/<name>*/split/s<k>.wav whose text is the line's say; a line may
      name its file with "wav": "<path>"), copies them to <out dir>/wav/s<i>.wav and writes <out dir>/spec.json for
      short_plan.py (wav_dir, sfx_dir=<out dir>/sfx, lipsync=python3). LOOK lines -> <out dir>/assemble.md
  python3 tools/short_auto.py silence <spec.json> <work dir> <out.md>
      0.6 s or longer silence inside a line (after short_plan.py), and the talk after the intro over 60 s.
  python3 tools/short_auto.py srt <plan.js> <out.srt>
      Japanese subtitles from the captions of plan.js (the same as channel/captions/*.srt so far).
  python3 tools/short_auto.py voicecheck <voice_report.json> <out.md>
      the report of tools/check_voice.py as RESULT / LOOK lines.
  python3 tools/short_auto.py collect <name> <out.md> <part.md> ...
      one report from the parts: RESULT OK only when every part is OK; all LOOK lines with the part's name."""
import glob, json, os, re, shutil, subprocess, sys, wave
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NORM = re.compile(r"[\s、。，．,.!?！？「」『』（）()・…ー〜~：:]")
JST = timezone(timedelta(hours=9))


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout


def lines_of(path):
    d = json.load(open(path, encoding="utf-8"))
    return [l for g in d["lines"] for l in g.split("\n") if l.strip()], len(d["lines"]), d.get("model", "gemini-3.8-flash-tts")


# ---------- TTS count ----------
def tts_count(name):
    subprocess.run(["git", "fetch", "-q", "origin", "+work:refs/remotes/origin/work"], cwd=ROOT, capture_output=True)
    day = datetime.now(JST).strftime("%Y-%m-%dT00:00:00+09:00")
    n = 0
    for blk in git("log", "origin/work", f"--since={day}", "--format=@%H", "--name-only", "--", "narration/").split("@")[1:]:
        sha, *files = [x for x in blk.split("\n") if x.strip()]
        for f in files:
            m = re.match(rf"^narration/({re.escape(name)}(?:_[^/]*)?)/tts_log\.txt$", f)
            if not m: continue
            try: n += max(1, len(json.loads(git("show", f"{sha}:narration/{m.group(1)}/lines.json"))["lines"]))
            except Exception: n += 1
    return n


# ---------- voice report ----------
def voice_report(name, lines_json, split_log, check_log, count, out):
    L, groups, model = lines_of(lines_json)
    sp = open(split_log, encoding="utf-8").read() if os.path.exists(split_log) else ""
    ck = open(check_log, encoding="utf-8").read() if os.path.exists(check_log) else ""
    looks = []
    if model != "gemini-3.8-flash-tts": looks.append(f"- LOOK lines.json｜モデルが {model}｜gemini-3.8-flash-tts だけを使う｜-")
    durs = {}
    for m in re.finditer(r"^s(\d+)\.wav ([\d.]+)s  (.*?)(?:   CHECK: (.*))?$", sp, re.M):
        durs[int(m.group(1))] = float(m.group(2))
        if m.group(4): looks.append(f"- LOOK s{m.group(1)}｜切れ目があやしい（{m.group(4)}）｜{m.group(3)[:40]}｜split_tts.py")
    heard = {}
    for m in re.finditer(r"^s(\d+) (LOOK )?([\d.]+)\n  script: (.*)\n  heard : (.*)$", ck, re.M):
        heard[int(m.group(1))] = (m.group(5), float(m.group(3)))
        if m.group(2):
            looks.append(f"- LOOK s{m.group(1)}｜聞こえた文が台本と違う（似ている度合い {m.group(3)}）｜台本「{m.group(4)}」｜聞こえた「{m.group(5)}」")
    if not durs: looks.append("- LOOK 全体｜分けられなかった｜-｜split_tts.py のログ（Actions の画面）")
    elif len(durs) != len(L): looks.append(f"- LOOK 全体｜分けた数 {len(durs)} と台本の文の数 {len(L)} が違う｜-｜split_tts.py")
    if ck and not heard: looks.append("- LOOK 全体｜文字起こしができなかった｜-｜check_split.py のログ")
    if int(count) > 3: looks.append(f"- LOOK 読み上げ回数｜今日この動画で {count} 回（上限3回）｜これ以上は作り直さない｜-")
    res = "OK" if not looks else "LOOK"
    out_l = [f"RESULT: {res}"] + looks + ["", f"読み上げの分割と確認：{name}（{os.path.dirname(lines_json)}、{len(L)}文・{groups}回分）　今日この動画の読み上げ：{count}回（上限3回）", "",
             "| 文 | 秒 | 聞こえた文（似ている度合い） |", "|---|---|---|"]
    for i in range(1, len(L) + 1):
        h = heard.get(i, ("", 0)); out_l.append(f"| s{i} | {durs.get(i, 0):.2f} | {h[0]}（{h[1]:.2f}） |")
    open(out, "w", encoding="utf-8").write("\n".join(out_l) + "\n")
    print("\n".join(out_l[:len(looks) + 1]))
    return 0 if res == "OK" else 1


# ---------- assemble ----------
def pattern(say):
    parts = [re.escape(NORM.sub("", p)) for p in say.split("{SEC}")]
    return re.compile("^" + "(?:[0-9０-９]+秒|1分|一分|[ぁ-んァ-ン一-龥0-9]{1,6})".join(parts) + "$")


def assemble(spec_path, name, out):
    spec = json.load(open(spec_path, encoding="utf-8"))
    os.makedirs(os.path.join(out, "wav"), exist_ok=True)
    dirs = [d for d in glob.glob(os.path.join(ROOT, "narration", name)) + glob.glob(os.path.join(ROOT, "narration", name + "_*")) if os.path.isdir(d)]
    def when(d):  # newest last: time of the last change on the branch work (else on disk)
        t = git("log", "-1", "--format=%ct", "origin/work", "--", os.path.relpath(d, ROOT)).strip()
        return (int(t) if t else int(os.path.getmtime(d)), d)
    dirs = [d for _, d in sorted(when(d) for d in dirs)]
    cands = []  # (normalized text, wav path, check LOOK?)
    for d in dirs:
        lj = os.path.join(d, "lines.json")
        if not os.path.exists(lj): continue
        L, groups, _ = lines_of(lj)
        sd = os.path.join(d, "split")
        if not os.path.exists(os.path.join(sd, "s1.wav")) and os.path.exists(os.path.join(d, "s1.wav")):
            if len(L) == 1: os.makedirs(sd, exist_ok=True); shutil.copy(os.path.join(d, "s1.wav"), os.path.join(sd, "s1.wav"))
            else: subprocess.run([sys.executable, os.path.join(ROOT, "tools", "split_tts.py"), lj, d, sd], capture_output=True)
        bad = set()
        if os.path.exists(os.path.join(sd, "check.txt")):
            bad = {int(m) for m in re.findall(r"^s(\d+) LOOK", open(os.path.join(sd, "check.txt"), encoding="utf-8").read(), re.M)}
        for k, l in enumerate(L, 1):
            p = os.path.join(sd, f"s{k}.wav")
            if os.path.exists(p): cands.append((NORM.sub("", l), p, k in bad))
    looks, used = [], []
    for i, ln in enumerate(spec["lines"], 1):
        if ln.get("fixed_wav"): used.append(f"s{i}: {ln['fixed_wav']}（使い回し）"); continue
        if ln.get("wav"):
            src = os.path.join(ROOT, ln["wav"])
            if os.path.exists(src): shutil.copy(src, os.path.join(out, "wav", f"s{i}.wav")); used.append(f"s{i}: {ln['wav']}"); continue
            looks.append(f"- LOOK 台本{i}行目｜指定の音声 {ln['wav']} がない｜-｜spec.json の wav"); continue
        say = ln.get("say", "")
        pat = pattern(say) if "{SEC}" in say else None
        hit = [c for c in cands if (pat.match(c[0]) if pat else c[0] == NORM.sub("", say))]
        good = [c for c in hit if not c[2]]
        pick = (good or hit or [None])[-1]
        if not pick:
            looks.append(f"- LOOK 台本{i}行目｜この文の読み上げがない（lines.json の文と say が違う）｜say「{say}」｜narration/{name}*/lines.json"); continue
        if pick[2]: looks.append(f"- LOOK 台本{i}行目｜使える音声が check_split で LOOK のものだけ｜{os.path.relpath(pick[1], ROOT)}｜say「{say[:30]}」")
        shutil.copy(pick[1], os.path.join(out, "wav", f"s{i}.wav")); used.append(f"s{i}: {os.path.relpath(pick[1], ROOT)}")
    spec["wav_dir"] = os.path.join(out, "wav"); spec["sfx_dir"] = os.path.join(out, "sfx"); spec["lipsync"] = "python3"
    json.dump(spec, open(os.path.join(out, "spec.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(out, "assemble.md"), "w", encoding="utf-8").write(
        f"RESULT: {'OK' if not looks else 'LOOK'}\n" + "\n".join(looks) + "\n\n使った音声：\n" + "\n".join("- " + u for u in used) + "\n")
    print("\n".join(looks) or "assemble: ok"); print("\n".join(used))


# ---------- silence ----------
def silence(spec_path, W, out):
    import numpy as np
    spec = json.load(open(spec_path, encoding="utf-8")); looks = []
    for i, ln in enumerate(spec["lines"], 1):
        p = os.path.join(W, f"l{i}.wav")
        if not os.path.exists(p): continue
        w = wave.open(p); sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        h = int(sr * 0.01); n = len(x) // h
        if n < 3: continue
        q = 20 * np.log10(np.sqrt((x[: n * h].reshape(n, h) ** 2).mean(1)) + 1e-9) < -40
        k = 0
        while k < n:
            j = k
            while j < n and q[j] == q[k]: j += 1
            if q[k] and k > 0 and j < n and (j - k) * 0.01 >= 0.6:
                looks.append(f"- LOOK 台本{i}行目｜文の中に{(j - k) * 0.01:.1f}秒の無音（{k * 0.01:.1f}秒目）｜無音は0.6秒未満｜「{ln.get('show', ln.get('say', ''))[:30]}」")
            k = j
    pj = os.path.join(W, "plan.js"); extra = ""
    if os.path.exists(pj):
        s = open(pj, encoding="utf-8").read(); P = json.loads(s[s.index("=") + 1:].rstrip("; \n"))
        intro = [l for l in P["lines"] if l.get("scene") == "intro"]
        after = P["voice_end"] - (intro[0]["end"] if intro else 0)
        if after > 60.05: looks.append(f"- LOOK 長さ｜登場のあと話し終わりまで {after:.1f}秒｜60秒以内｜plan.js")
        extra = f"動画 {P['T']:.1f}秒・話し終わり {P['voice_end']:.1f}秒（登場のあと {after:.1f}秒）・字幕 {len(P['tel'])}回"
    open(out, "w", encoding="utf-8").write(f"RESULT: {'OK' if not looks else 'LOOK'}\n" + "\n".join(looks) + f"\n\n長さと無音：{extra}\n")
    print("\n".join(looks) or "silence: ok", extra)


# ---------- srt ----------
def srt(plan, out):
    s = open(plan, encoding="utf-8").read(); P = json.loads(s[s.index("=") + 1:].rstrip("; \n")); tel = P["tel"]
    ts = lambda t: f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d},{int(round(t % 1 * 1000)) % 1000:03d}"
    o = []
    for i, c in enumerate(tel):
        end = tel[i + 1]["start"] if i + 1 < len(tel) else c["end"]
        o.append(f"{i + 1}\n{ts(c['start'])} --> {ts(end)}\n{c['text']}\n")
    open(out, "w", encoding="utf-8").write("\n".join(o))


# ---------- voice check (tools/check_voice.py report) ----------
def voicecheck(rep, out):
    try: r = json.load(open(rep, encoding="utf-8"))
    except Exception:
        open(out, "w", encoding="utf-8").write("RESULT: FAILED\n- LOOK 全体｜声の確認が動かなかった｜voice-check.yml で動かす｜-\n"); return 2
    big = r.get("issues", []); adj = r.get("similarity_adjusted", 0)
    looks = [f"- LOOK 台本{x['line']}行目｜{x['kind']}｜台本「{x['expected']}」（{x['say'][:24]}）｜聞こえた「{x['heard']}」…{x['context_heard']}…" for x in big]
    if adj < 0.95: looks.insert(0, f"- LOOK 全体｜似ている度合い（調整後）{adj}｜0.95以上｜check_voice.py")
    body = [f"RESULT: {'OK' if not looks else 'LOOK'}"] + looks + ["", f"声の確認：似ている度合い {r.get('similarity')}（調整後 {adj}）。ずれは1字でも台本の say と見比べて理由を書く（数字・英語の書き方の違いは問題なし）", ""]
    body += [f"- 表記の違い 台本{x['line']}行目：「{x['expected']}」→「{x['heard']}」" for x in r.get("notation", [])]
    open(out, "w", encoding="utf-8").write("\n".join(body) + "\n"); print("\n".join(body)); return 0 if not looks else 1


# ---------- collect ----------
PART = {"assemble": "声のつなぎ", "silence": "長さと無音", "plan": "台本の秒数", "fit": "はみ出し", "big": "大きいりな", "render": "書き出し",
        "voice": "声", "frames": "画面", "facts": "事実", "longcat": "締めの話す動画"}


def collect(name, out, parts):
    res, looks, notes = "OK", [], []
    for p in parts:
        if not os.path.exists(p): continue
        key = os.path.splitext(os.path.basename(p))[0]; lab = PART.get(key, key)
        t = open(p, encoding="utf-8").read().strip().split("\n"); first = t[0].strip() if t else ""
        r = (re.findall(r"RESULT:\s*([A-Z]+)", first) or ["FAILED"])[0]
        notes.append(f"- {lab}：{r}")
        if r == "OK": continue
        res = "LOOK"
        ls = [l for l in t[1:] if l.startswith("- LOOK")]
        if r == "FAILED":
            ls = ls or [f"- LOOK {lab}｜自動の確認が答えを出せなかった（FAILED）｜従来の手順で確認｜checks/{name}/{key}.md"]
        looks += [l.replace("- LOOK ", f"- LOOK [{lab}] ", 1) for l in ls] or [f"- LOOK [{lab}] {r}｜詳しくは checks/{name}/{key}.md｜-｜-"]
    planned = any(os.path.basename(p) == "plan.md" and os.path.exists(p) and open(p, encoding="utf-8").read().startswith("RESULT: OK") for p in parts)
    missing = [] if not planned else [PART.get(k, k) for k in ("assemble", "silence", "fit", "render", "voice", "frames", "facts") if not any(os.path.splitext(os.path.basename(p))[0] == k and os.path.exists(p) for p in parts)]
    if missing:
        res = "LOOK"; looks.append(f"- LOOK [全体] 結果が届かなかった確認：{'、'.join(missing)}｜Actions の画面で失敗した段を見る｜-｜-")
    body = [f"RESULT: {res}"] + looks + ["", f"ショートの自動の書き出しと確認：{name}", *notes, "",
            f"完成動画：ブランチ work の final/{name}.mp4（1秒ごとのコマ一覧は final/{name}_sheets/）。各確認の詳細はブランチ checks の checks/{name}/"]
    open(out, "w", encoding="utf-8").write("\n".join(body) + "\n")
    print("\n".join(body))
    return 0 if res == "OK" else 1


if __name__ == "__main__":
    c, a = (sys.argv[1] if len(sys.argv) > 1 else ""), sys.argv[2:]
    if c == "tts-count": print(tts_count(a[0]))
    elif c == "voice-report": sys.exit(voice_report(*a[:6]))
    elif c == "assemble": assemble(*a[:3])
    elif c == "silence": silence(*a[:3])
    elif c == "srt": srt(*a[:2])
    elif c == "voicecheck": sys.exit(voicecheck(*a[:2]))
    elif c == "collect": sys.exit(collect(a[0], a[1], a[2:]))
    else: print(__doc__); sys.exit(2)
