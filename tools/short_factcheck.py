"""Fact check of a Short by Codex (2026-11-14, the user's request: save Claude's quota, same quality).
Replaces the Claude Sonnet sub-agent of tools/auto_short.md 3-3. Used by .github/workflows/codex-short-factcheck.yml.

  python3 tools/short_factcheck.py prep <job dir> --name N [--script S] [--meta M] [--srt R] [--refs "ED/id ..."] [--extra "branch:path ..."]
      writes <job dir>/video.txt (what the video says: script say+show, captions, title, description, tags),
      <job dir>/refs.txt (the reference texts) and copies the task. Paths may be "<branch>:<path>" (e.g. work:x/spec.json).
      refs: for every ED/id -> data/<ED>.json article (main), research/<ED>/<id>.txt (branch research),
            factcheck/<ED>/<id>.txt (branch factcheck). extra: more texts, e.g. fetched:fetched/<x>/page.txt
  python3 tools/short_factcheck.py report <job dir> <name> <out.md>
      reads <job dir>/result.json (written by Codex) and writes the Japanese report:
      first line 「RESULT: OK」|「RESULT: LOOK」|「RESULT: FAILED」, then 「- LOOK 場所｜何が｜正しい値｜出どころ」.
      exit 0 = OK, 1 = LOOK, 2 = FAILED (Codex gave no valid answer -> use the old Claude Sonnet check)."""
import argparse, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(spec):
    """'branch:path' (read from origin/<branch>) or a path in the checkout. Returns '' if missing."""
    if not spec: return ""
    m = re.match(r"^([A-Za-z0-9_.-]+):(.+)$", spec)
    if m and not os.path.exists(spec):
        b, p = m.groups()
        subprocess.run(["git", "fetch", "-q", "origin", f"+{b}:refs/remotes/origin/{b}"], cwd=ROOT, capture_output=True)
        r = subprocess.run(["git", "show", f"origin/{b}:{p}"], cwd=ROOT, capture_output=True)
        return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else ""
    p = spec if os.path.isabs(spec) else os.path.join(ROOT, spec)
    return open(p, encoding="utf-8", errors="replace").read() if os.path.exists(p) else ""


def flat(x):
    if isinstance(x, str): return x
    if isinstance(x, list): return "\n".join(flat(y) for y in x)
    if isinstance(x, dict): return "\n".join(flat(v) for k, v in x.items() if k not in ("url", "image", "img", "src", "gallery", "visual", "diagram"))
    return str(x) if x is not None else ""


def prep(a):
    os.makedirs(a.job, exist_ok=True)
    out, missing = [], []
    s = read(a.script or f"shorts/{a.name}/spec.json")
    if s:
        try:
            d = json.loads(s); L = d.get("lines", d) if isinstance(d, dict) else d
            out.append("## 台本（1行ずつ。say＝読み上げ、show＝画面の字幕）")
            for i, x in enumerate(L, 1):
                if isinstance(x, str): out.append(f"{i}. {x}"); continue
                say, show = (x.get("say") or "").replace("{SEC}", "（秒数）"), (x.get("show") or x.get("say") or "").replace("{SEC}", "（秒数）")
                out.append(f"{i}. [{x.get('scene', '')}] say: {say}" + (f"\n   show: {show}" if show != say else ""))
        except Exception:
            out.append("## 台本\n" + s[:8000])
    else: missing.append("台本")
    r = read(a.srt or f"channel/captions/{a.name}_ja.srt")
    if r:
        out.append("\n## 字幕（SRT の文字だけ、出る順）")
        out.append(" / ".join(l.strip() for l in r.splitlines() if l.strip() and not l.strip().isdigit() and "-->" not in l))
    m = read(a.meta or f"channel/meta/{a.name}.json")
    if m:
        try:
            d = json.loads(m)
            out.append("\n## タイトル\n" + d.get("title", ""))
            out.append("\n## 概要欄\n" + d.get("description", ""))
            if d.get("tags"): out.append("\n## タグ\n" + "、".join(d["tags"]))
            if d.get("title_en") or d.get("description_en"):
                out.append("\n## 英語のタイトル・概要欄\n" + d.get("title_en", "") + "\n" + d.get("description_en", ""))
            if d.get("comment"): out.append("\n## 固定コメント\n" + d["comment"])
        except Exception:
            out.append("\n## タイトル・概要欄\n" + m[:6000])
    else: missing.append("タイトル・概要欄")
    if a.text: out.append("\n## そのほかの文字（サムネなど）\n" + a.text)
    open(os.path.join(a.job, "video.txt"), "w", encoding="utf-8").write("\n".join(out) + "\n")

    refs = []
    for r in (a.refs or "").split():
        if "/" not in r: continue
        ed, aid = r.split("/", 1)
        try:
            d = json.loads(read(f"data/{ed}.json") or "{}")
            for art in d.get("articles", []):
                if art.get("id") == aid:
                    keep = {k: art.get(k) for k in ("title", "summary", "published", "source_name", "body")}
                    refs.append((f"マイ夕刊の記事 data/{ed}.json {aid}（点検済みの記事。出典 {art.get('source_name', '')}）", flat(keep)))
        except Exception: pass
        for br in ("research", "factcheck"):
            t = read(f"{br}:{br}/{ed}/{aid}.txt")
            if t: refs.append((f"{br}/{ed}/{aid}.txt（元記事・参考記事のページ本文）", t))
    for x in (a.extra or "").split():
        t = read(x)
        if t: refs.append((x, t))
        else: missing.append(x)
    with open(os.path.join(a.job, "refs.txt"), "w", encoding="utf-8") as f:
        for name, t in refs: f.write(f"\n########## {name}\n{t.strip()}\n")
    meta = {"name": a.name, "refs": [n for n, _ in refs], "missing": missing}
    json.dump(meta, open(os.path.join(a.job, "inputs.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(meta, ensure_ascii=False))
    if not refs: print("no reference text"); sys.exit(3)


def report(job, name, out):
    meta = json.load(open(os.path.join(job, "inputs.json"), encoding="utf-8")) if os.path.exists(os.path.join(job, "inputs.json")) else {}
    log = open(os.path.join(job, "codex.log"), encoding="utf-8", errors="replace").read() if os.path.exists(os.path.join(job, "codex.log")) else ""
    used = (re.findall(r"(?m)^model:\s*(\S+)", log) or re.findall(r"(?m)^--- attempt \d+ model=(\S+)", log) or ["?"])[-1]
    if used == "None": used = "アカウントの既定のモデル（指定のモデルは断られた）"
    eff = (re.findall(r"(?m)^reasoning effort:\s*(\S+)", log) or [os.environ.get("EFFORT", "?")])[-1]
    res, code = None, 2
    try:
        res = json.load(open(os.path.join(job, "result.json"), encoding="utf-8"))
        assert res["result"] in ("OK", "LOOK") and isinstance(res.get("items", []), list)
    except Exception as e:
        res = None
    L = []
    if res is None:
        L.append("RESULT: FAILED")
        L.append("")
        L.append("Codex から正しい答え（result.json）が返りませんでした。従来どおり、作った本人ではない Claude Sonnet のサブエージェントで事実確認をしてください。")
    else:
        items = [x for x in res.get("items", []) if isinstance(x, dict)]
        ok = res["result"] == "OK" and not items
        code = 0 if ok else 1
        L.append("RESULT: " + ("OK" if ok else "LOOK"))
        for x in items:
            c = lambda k: re.sub(r"[｜\n]+", " ", str(x.get(k, "")).strip())
            L.append(f"- LOOK {c('where')}｜{c('what')}｜{c('correct')}｜{c('source')}")
        L.append("")
        L.append(f"確かめた事実の数：{res.get('checked', '?')}　/　{res.get('note', '')}".rstrip("　/ "))
    L.append("")
    L.append(f"事実確認（Codex {used}・effort {eff}）　対象：{name}")
    if meta.get("refs"): L.append("照らした資料：" + "、".join(meta["refs"]))
    if meta.get("missing"): L.append("見つからなかった入力：" + "、".join(meta["missing"]))
    open(out, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))
    sys.exit(code)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "report": report(*sys.argv[2:5])
    elif len(sys.argv) > 1 and sys.argv[1] == "prep":
        ap = argparse.ArgumentParser(); ap.add_argument("cmd"); ap.add_argument("job"); ap.add_argument("--name", required=True)
        for k in ("script", "meta", "srt", "refs", "extra", "text"): ap.add_argument("--" + k, default="")
        prep(ap.parse_args())
    else: print(__doc__); sys.exit(2)
