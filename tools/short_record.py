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


def man(n):
    return f"{n / 10000:.1f}万"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--from", dest="frm")
    ap.add_argument("--to")
    ap.add_argument("--transcript")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
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
