#!/usr/bin/env python3
"""ショート1本の作業記録の「数字」を集める（2026-11-21〜）。

使い方（リポジトリの一番上で）:
  python3 tools/short_record.py <名前>                  # 例 rina_donki_ai。表を出すだけ
  python3 tools/short_record.py <名前> --write          # tools/learning/shorts/<名前>.md の「数字」を書き換える（無ければひな形から作る）
  --from / --to  2026-11-21T08:38Z の形（UTC）。省略時：from＝そのショートの最初のコミット、to＝今
  --transcript <jsonl>  Claude の会話の記録。省略時は ~/.claude/projects の一番新しいものを使う（見つからなければ省く）

集めるもの：かかった時間、GitHub の自動作業の回数（作業ごと・失敗の数・合計分）、
書き出し（short-build）と読み上げ（narration）の回数、Claude の使った量（会話の記録があるとき）。
Claude はこの表を読むだけでよい（自分で数え直さない）。
"""
import argparse, datetime as dt, glob, json, os, re, subprocess, sys

REPO = "pasta0725/my-yukan"
JST = dt.timezone(dt.timedelta(hours=9))
# ショートづくりに使う自動作業（ワークフローの name）
SHORT_WF = re.compile(r"short|narration|longcat|codex-(short|frame|images)|fetch-(media|to-branch)|voice|youtube-upload|after-public|tts")
MARK_A, MARK_B = "<!-- 数字ここから（short_record.py が書く） -->", "<!-- 数字ここまで -->"


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True).stdout.strip()


def parse(t):
    t = t.replace("Z", "+00:00")
    if re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d\+00:00", t):
        t = t.replace("+00:00", ":00+00:00")
    return dt.datetime.fromisoformat(t)


def first_commit(name):
    paths = [f"shorts/{name}", f"narration/{name}", f"channel/meta/{name}.json"]
    out = sh("git", "log", "--reverse", "--format=%cI", "--", *paths)
    return parse(out.splitlines()[0]) if out else None


def talking(frm, to):
    """話す動画（LongCat）を Colab と Modal のどちらで作ったか。short-build / longcat-colab の記録から読む（2026-11-21）。"""
    frm, to = frm.astimezone(dt.timezone.utc), to.astimezone(dt.timezone.utc)
    q = f"repos/{REPO}/actions/runs?per_page=100&created={frm:%Y-%m-%dT%H:%M:%SZ}..{to:%Y-%m-%dT%H:%M:%SZ}"
    ids = sh("gh", "api", "--paginate", q, "-q", '.workflow_runs[]|select(.name=="short-build" or .name=="longcat-colab")|.id').split()
    out = []
    for rid in reversed(ids):
        js = sh("gh", "api", f"repos/{REPO}/actions/runs/{rid}/jobs", "-q",
                r'.jobs[]|select(.name|test("longcat|run"))|select(.steps|map(.name)|index("run on Colab"))|"\(.id)\t\(.started_at)\t\(.completed_at)\t\(.conclusion)"')
        for line in js.splitlines():
            jid, a, b, c = line.split("\t")
            log = [l[29:] for l in sh("gh", "api", f"repos/{REPO}/actions/jobs/{jid}/logs").splitlines() if "[36;1m" not in l and "##[" not in l]
            pick = lambda pat: next((l.strip() for l in log if re.search(pat, l)), "")
            if pick(r"^Colab made the clips"):
                via, why = "Colab", ""
            elif pick(r"^no clip from Colab"):
                via = "Modal"
                why = "・".join(x for x in (pick(r"^no Colab GPU after"), pick(r"giving up Colab"), pick(r"timeout|35 min|cut off"), pick(r"^missing:")) if x)
            else:
                via, why = "不明（記録に結果の行なし）", c
            m = (parse(b) - parse(a)).total_seconds() / 60 if b and b != "null" else 0
            out.append(f"{parse(a).astimezone(JST):%m/%d %H:%M} {via}（約{m:.0f}分）" + (f"：{why[:160]}" if why else ""))
    return out


def history(name, frm, to):
    """そのショートのコミットの一覧（何をいつ直したか）。"""
    paths = [f"shorts/{name}", f"narration/{name}", f"narration/{name}_fix1", f"narration/{name}_fix2", f"narration/{name}_fix3", f"channel/meta/{name}.json"]
    out = sh("git", "log", "--reverse", f"--since={frm.isoformat()}", f"--until={to.isoformat()}", "--format=%cI\t%s", "--", *paths)
    return [(parse(t), m) for t, m in (l.split("\t", 1) for l in out.splitlines())]


# 工程の順番：(工程, 使う自動作業の name, 道具・機械)。台本と画面の設計は Claude（自動作業の合間の時間）
STEPS = [
    ("素材（公式の画像・元記事）", ("fetch-media", "fetch-to-branch"), "GitHub（取り込み）"),
    ("事実確認", ("codex-short-factcheck",), "Codex gpt-6.2-sol"),
    ("声（読み上げ・切り分け）", ("narration", "short-voice"), "Gemini 読み上げ（Leda）＋文字起こし"),
    ("サムネ", ("codex-images", "short-thumb-check"), "Codex の画像づくり・公開後の確認"),
    ("書き出しと確認（画面・字幕・声・話す動画）", ("short-build", "codex-frame-check", "voice-check", "longcat-colab"), "GitHub で書き出し＋Codex の画面確認＋Colab/Modal"),
    ("投稿", ("short-upload", "youtube-upload", "after-public"), "YouTube（予約・サムネ・固定コメント）"),
]


def steps_table(rs, hist, frm, to):
    L = ["  | 工程 | 道具・機械 | 回数 | やり直し | 分 | やり直しの前に直したこと |", "  |---|---|---|---|---|---|"]
    busy = []
    for title, wfs, tool in STEPS:
        mine = sorted([r for r in rs if r[0] in wfs and r[0] not in ("after-public", "short-thumb-check", "voice-check", "codex-frame-check") or (r[0] in wfs and len(wfs) == 1)], key=lambda r: r[2])
        allr = [r for r in rs if r[0] in wfs]
        if not allr:
            continue
        main_r = [r for r in allr if r[0] == wfs[0]] or allr
        mins = sum(max(0, (e - s).total_seconds() / 60) for n, c, s, e in allr if n not in ("after-public", "short-thumb-check"))
        busy += [(s, e) for n, c, s, e in allr if n not in ("after-public", "short-thumb-check")]
        why = []
        for n, c, s, e in sorted(main_r, key=lambda r: r[2])[1:]:
            before = [m for t, m in hist if t <= s and not m.startswith("ショート自動")]
            why.append(before[-1][:60] if before else "？")
        fails = sum(c not in ("success", "skipped", "running") for n, c, s, e in main_r)
        L.append(f"  | {title} | {tool} | {len(main_r)} | {len(main_r) - 1}（要確認・失敗{fails}） | {mins:.0f} | {' / '.join(why) or '-'} |")
    # Claude の作業時間＝自動作業が動いていない時間（台本・場面の設計・直し・判断）
    busy.sort()
    used, cur = 0.0, None
    for s, e in busy:
        s, e = max(s, frm), min(e, to)
        if e <= s:
            continue
        if cur and s <= cur[1]:
            cur[1] = max(cur[1], e)
        else:
            if cur:
                used += (cur[1] - cur[0]).total_seconds()
            cur = [s, e]
    if cur:
        used += (cur[1] - cur[0]).total_seconds()
    claude = ((to - frm).total_seconds() - used) / 60
    L.insert(2, f"  | 台本・場面の設計と直し | Claude（親） | - | - | {claude:.0f}（自動作業が何も動いていない時間。待ちの間の作業は含まない） | 下の「直した履歴」 |")
    return L


def runs(frm, to):
    frm, to = frm.astimezone(dt.timezone.utc), to.astimezone(dt.timezone.utc)
    q = f"repos/{REPO}/actions/runs?per_page=100&created={frm:%Y-%m-%dT%H:%M:%SZ}..{to:%Y-%m-%dT%H:%M:%SZ}"
    out = sh("gh", "api", "--paginate", q, "-q", ".workflow_runs[]|[.name,.conclusion,.created_at,.updated_at]|@tsv")
    rows = []
    for line in out.splitlines():
        n, c, a, b = (line.split("\t") + ["", "", "", ""])[:4]
        if SHORT_WF.search(n):
            rows.append((n, c or "running", parse(a), min(parse(b), to)))
    return rows


def usage(path, frm, to):
    files = [path] + glob.glob(os.path.join(path[:-6], "subagents", "*.jsonl"))
    tot = dict(new=0, cache=0, out=0, tools=0, sub=0)
    for i, f in enumerate(files):
        if not os.path.exists(f):
            continue
        for l in open(f, encoding="utf-8"):
            try:
                d = json.loads(l)
            except ValueError:
                continue
            if d.get("type") != "assistant" or "timestamp" not in d:
                continue
            t = parse(d["timestamp"][:19] + "+00:00")
            if not (frm <= t <= to):
                continue
            u = d["message"].get("usage") or {}
            tot["new"] += u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
            tot["cache"] += u.get("cache_read_input_tokens", 0)
            tot["out"] += u.get("output_tokens", 0)
            n = sum(1 for c in d["message"].get("content", []) if isinstance(c, dict) and c.get("type") == "tool_use")
            tot["tools"] += n
            if i:
                tot["sub"] += n
    return tot


STEP_KEYS = [
    ("記事選び", r"next_short|params\.json|data/\d{4}-\d\d-\d\d-(am|pm)\.json|shorts_log"),
    ("素材", r"fetch-media|fetch-to-branch|work_branch\.py get|media/"),
    ("事実確認", r"factcheck"),
    ("声", r"narration|tts|short-voice|split_tts|check_split|lines\.json|--check-captions"),
    ("話す動画", r"longcat"),
    ("サムネ", r"thumb|codex-images"),
    ("画面と字幕", r"preview\.js|check_fit|short\.html|plan\.js|spec\.json"),
    ("書き出しと確認", r"short-build|frame-check|voice-check|build\.md"),
    ("投稿", r"short-upload|youtube-upload|after-public|channel/meta"),
]


def step_of(text):
    return next((k for k, pat in STEP_KEYS if re.search(pat, text)), "その他")


def flow(path, frm, to):
    """会話の記録から、何をどの順で行ったか（動かした作業と設定・道具・コミット・読んだファイル）を短く並べる。"""
    files = [path] + glob.glob(os.path.join(path[:-6], "subagents", "*.jsonl"))
    ev, reads = [], {}
    for i, f in enumerate(files):
        for l in open(f, encoding="utf-8"):
            try:
                d = json.loads(l)
            except ValueError:
                continue
            if d.get("type") != "assistant" or "timestamp" not in d:
                continue
            t = parse(d["timestamp"][:19] + "+00:00")
            if not (frm <= t <= to):
                continue
            for c in d["message"].get("content", []):
                if not (isinstance(c, dict) and c.get("type") == "tool_use"):
                    continue
                n, x = c.get("name", ""), c.get("input", {})
                who = "助手 " if i else ""
                if n == "Bash":
                    full = x.get("command", "")
                    if re.search(r"python3? -\s*<<", full):
                        ps = sorted(set(re.findall(r"""(?:p\s*=\s*|open\()['"]([\w./-]+\.\w+)['"]""", full)))
                        if ps:
                            ev.append((t, step_of(" ".join(ps)), who + "スクリプトで書き換え：" + "・".join(ps)[:160]))
                    for cmd in re.split(r"\s*(?:&&|;|\n)\s*", x.get("command", "")):
                        cmd = re.sub(r"\s+", " ", cmd).strip()
                        cmd = re.sub(r"^(?:[A-Z_]+=\S+ )+", "", cmd).split(" | ")[0].split(" >")[0]
                        if re.match(r"python3? (?:-I )?tools/short_record\.py", cmd):
                            continue
                        m = re.match(r"gh workflow run \S+.*|gh run watch.*|python3? (?:-I )?tools/\S+.*|node \S+.*|git (?:-c \S+ )*commit .*?-m ?[\"']([^\"'\n]{0,80})", cmd)
                        if m:
                            ev.append((t, step_of(cmd), who + (("コミット：" + m.group(1)) if m.group(1) else m.group(0)[:160])))
                elif n in ("Read", "Edit", "Write", "NotebookEdit"):
                    fp = x.get("file_path", "").split("my-yukan/")[-1]
                    reads.setdefault((n, fp), []).append(t)
                    if n != "Read":
                        ev.append((t, step_of(fp), f"{who}{'書き換え' if n == 'Edit' else '新しく書く'}：{fp}"))
                elif n == "Agent":
                    ev.append((t, "その他", f"助手に任せた：{x.get('description', '')}（{x.get('model', '既定')}）"))
    ev.sort()
    out, last = [], None
    for t, st, txt in ev:   # 同じ操作が続いたら1行にまとめる
        if last and last[1] == st and last[2] == txt:
            last[3] += 1
            continue
        last = [t, st, txt, 1]
        out.append(last)
    lines = [f"  {k}. {t.astimezone(JST):%H:%M}〔{st}〕{txt}" + (f" ×{r}" if r > 1 else "") for k, (t, st, txt, r) in enumerate(out, 1)]
    again = [f"{fp}×{len(v)}" for (n, fp), v in reads.items() if n == "Read" and len(v) > 1]
    return lines, again


def man(n):
    return f"{n / 10000:.1f}万"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--from", dest="frm")
    ap.add_argument("--to")
    ap.add_argument("--transcript")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--note", help="作りながら手順と判断を1行足す：'工程｜何を・どうやって（コマンド・設定）→結果｜なぜ'")
    a = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    if a.note:
        p = f"tools/learning/shorts/{a.name}.md"
        if not os.path.exists(p):
            open(p, "w", encoding="utf-8").write(open("tools/learning/shorts/_template.md", encoding="utf-8").read().replace("<名前>", a.name))
        s = open(p, encoding="utf-8").read()
        head = "## 手順と判断（作りながら --note で足す）\n"
        line = f"- {now.astimezone(JST):%m/%d %H:%M}｜{a.note.strip()}\n"
        if head not in s:
            s = s.replace("## 数字", head + "\n## 数字", 1)
        i = s.index(head) + len(head)
        j = s.find("\n## ", i)
        j = len(s) if j < 0 else j
        s = s[:j].rstrip("\n") + "\n" + line + s[j:] if s[i:j].strip() else s[:i] + line + s[i:]
        open(p, "w", encoding="utf-8").write(s)
        return
    frm = parse(a.frm) if a.frm else first_commit(a.name)
    if not frm:
        sys.exit("最初のコミットが見つかりません。--from を付けてください")
    to = parse(a.to) if a.to else now
    rs = runs(frm, to)
    mins = (to - frm).total_seconds() / 60
    L = [MARK_A, f"- かかった時間：{frm.astimezone(JST):%m/%d %H:%M}〜{to.astimezone(JST):%H:%M}（日本時間）＝約{mins:.0f}分"]
    h = history(a.name, frm, to)
    L.append("- 工程ごと（回数は主な自動作業の回数。分は待ちも含む）：")
    L += steps_table(rs, h, frm, to)
    tk = talking(frm, to)
    i = next((k for k, x in enumerate(L) if x.startswith("  | 書き出しと確認")), len(L))
    L.insert(i, f"  | 話す動画（つかみ・締め） | LongCat：{'・'.join(x.split(' ', 2)[2] for x in tk) if tk else 'この時間に作っていない（前のものを使った）'} | {len(tk)} | {max(0, len(tk) - 1)} | （書き出しの分に含む） | 下の「話す動画」 |")
    L.append("- 話す動画（つかみ・締め）：" + ("なし（作らなかった／前のものを使った）" if not tk else ""))
    L += [f"  - {x}" for x in tk]
    L.append(f"- 直した履歴（コミット{len(h)}件）：")
    L += [f"  - {t.astimezone(JST):%H:%M} {m[:100]}" for t, m in h[:25]]
    tp = a.transcript
    if not tp:
        c = sorted(glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")), key=os.path.getmtime)
        tp = c[-1] if c else None
    u = usage(tp, frm, to) if tp and os.path.exists(tp) else None
    if u and u["tools"]:
        fl, again = flow(tp, frm, to)
        L.append(f"- 操作の流れ（会話の記録から自動。動かした作業と設定・道具・書き換えたファイル・コミットを順に。{len(fl)}行）：")
        L += fl[:120] + (["  …（120行より後は省略）"] if len(fl) > 120 else [])
        L.append("- 同じファイルを読み直した所（利用枠のむだの候補）：" + ("・".join(again) if again else "なし"))
    if u and u["tools"]:
        L.append(f"- Claude の使った量：新しく読んだ{man(u['new'])}・書いた{man(u['out'])}・読み直し（キャッシュ）{man(u['cache'])}・操作{u['tools']}回（うち助手{u['sub']}回）")
    else:
        L.append("- Claude の使った量：会話の記録が見つからず不明（分かれば手で書く）")
    L.append(MARK_B)
    block = "\n".join(L)
    print(block)
    if a.write:
        p = f"tools/learning/shorts/{a.name}.md"
        if not os.path.exists(p):
            t = open("tools/learning/shorts/_template.md", encoding="utf-8").read()
            open(p, "w", encoding="utf-8").write(t.replace("<名前>", a.name))
        s = open(p, encoding="utf-8").read()
        s = re.sub(re.escape(MARK_A) + r".*?" + re.escape(MARK_B), lambda m: block, s, flags=re.S) if MARK_A in s else s + "\n" + block + "\n"
        open(p, "w", encoding="utf-8").write(s)
        print("書いた:", p)


if __name__ == "__main__":
    main()
