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
    by = {}
    for n, c, s, e in rs:
        b = by.setdefault(n, [0, 0, 0.0])
        b[0] += 1
        b[1] += c not in ("success", "skipped", "running")
        b[2] += max(0, (e - s).total_seconds() / 60)
    L.append(f"- 自動作業：合計{len(rs)}回（うち失敗・要確認{sum(v[1] for v in by.values())}回）")
    L.append("  | 作業 | 回数 | 失敗・要確認 | 合計分 |")
    L.append("  |---|---|---|---|")
    for n, (k, f, m) in sorted(by.items(), key=lambda x: -x[1][2]):
        L.append(f"  | {n} | {k} | {f} | {m:.0f} |")
    L.append(f"- 書き出し（short-build）{by.get('short-build', [0])[0]}回・読み上げ（narration）{by.get('narration', [0])[0]}回")
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
