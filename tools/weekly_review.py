"""Helpers for codex-weekly-review.yml (2026-11-14, the user's request: move the weekly review 「週1回の見直し」 from Claude to
Codex to save Claude usage, quality must not drop). The rules are tools/learning/README.md. Never reads or prints secrets.

  python3 tools/weekly_review.py prep <metrics branch dir> <job dir>
      copies what the review reads into <job dir>: metrics/ (last 28 days), competitors/ (last 2), channel/shorts_log.csv,
      tools/learning/ (README, params.json, changelog.md, reports/), issues.md (open AIからの報告, as data), info.md.
  python3 tools/weekly_review.py check <job dir> <out dir>
      checks Codex's output: report.md must exist; params.json may only change "value"s, each inside min..max, by at most
      step, the category_limits total unchanged, publish_time one of choices. Writes <out dir>/check.json and, if valid,
      <out dir>/params.json + changelog_add.md (otherwise the params change is dropped and the report says so).
"""
import datetime, glob, json, os, re, shutil, subprocess, sys

JST = datetime.timezone(datetime.timedelta(hours=9))
REPO = os.environ.get("GITHUB_REPOSITORY", "pasta0725/my-yukan")


def cmd_prep(mdir, job):
    now = datetime.datetime.now(JST)
    y, w, _ = now.isocalendar()
    os.makedirs(f"{job}/metrics", exist_ok=True); os.makedirs(f"{job}/competitors", exist_ok=True)
    cut = (now - datetime.timedelta(days=28)).strftime("%Y-%m-%d")
    ms = sorted(f for f in glob.glob(f"{mdir}/metrics/*.json") if os.path.basename(f)[:10] >= cut)
    for f in ms: shutil.copy(f, f"{job}/metrics/")
    cs = sorted(glob.glob(f"{mdir}/competitors/*.json"))[-2:]
    for f in cs: shutil.copy(f, f"{job}/competitors/")
    os.makedirs(f"{job}/channel", exist_ok=True); shutil.copy("channel/shorts_log.csv", f"{job}/channel/")
    shutil.copytree("tools/learning", f"{job}/learning", dirs_exist_ok=True)
    for f in ("usage_log.csv",):
        if os.path.exists(f"{job}/learning/{f}"): os.remove(f"{job}/learning/{f}")
    lines = []
    try:
        out = subprocess.run(["gh", "api", "-X", "GET", f"repos/{REPO}/issues", "-f", "labels=AIからの報告", "-f", "state=open", "-f", "per_page=50"],
                             capture_output=True, text=True, check=True).stdout
        for it in json.loads(out):
            lines += [f"# #{it['number']} {it['title']}（更新 {it['updated_at']}、コメント {it['comments']}件）", (it.get("body") or "")[:3000], ""]
            if it["comments"]:
                cs_ = json.loads(subprocess.run(["gh", "api", f"repos/{REPO}/issues/{it['number']}/comments"], capture_output=True, text=True).stdout or "[]")
                for c in cs_[-4:]: lines += [f"## コメント {c['created_at']}", (c.get("body") or "")[:1500], ""]
    except Exception as e:
        lines = [f"(issues could not be read: {type(e).__name__})"]
    open(f"{job}/issues.md", "w", encoding="utf-8").write("\n".join(lines) + "\n")
    report = f"{y}-W{w:02d}.md"
    open(f"{job}/info.md", "w", encoding="utf-8").write(
        f"today (Japan time): {now:%Y-%m-%d %a}\nreport file name: {report}\nfirst Monday of the month: {'yes' if now.day <= 7 and now.weekday() == 0 else 'no'}\n"
        f"metrics files: {len(ms)} (from {os.path.basename(ms[0])[:10] if ms else '-'} to {os.path.basename(ms[-1])[:10] if ms else '-'})\n"
        f"competitors files: {', '.join(os.path.basename(f) for f in cs) or 'none'}\n"
        f"past weekly reports: {', '.join(sorted(x for x in os.listdir(f'{job}/learning/reports') if not x.startswith('.'))) or 'none (this is the first)'}\n")
    open(os.environ.get("GITHUB_OUTPUT", "/dev/null"), "a").write(f"report={report}\n")
    print("prepared", report, len(ms), "metrics,", len(cs), "competitors")


def leaves(d, path=()):
    if isinstance(d, dict) and "value" in d: yield path, d; return
    if isinstance(d, dict):
        for k, v in d.items(): yield from leaves(v, path + (k,))


def cmd_check(job, out):
    os.makedirs(out, exist_ok=True)
    res = {"report": False, "params": "unchanged", "problems": [], "changes": []}
    rep = f"{job}/report.md"
    res["report"] = os.path.exists(rep) and len(open(rep, encoding="utf-8").read().strip()) > 200
    if not res["report"]: res["problems"].append("週報（report.md）が無い・短すぎる")
    old = json.load(open("tools/learning/params.json"))
    try: new = json.load(open(f"{job}/learning/params.json"))
    except Exception as e: new = old; res["problems"].append(f"params.json が壊れている（{type(e).__name__}）")
    po = dict(leaves(old)); pn = dict(leaves(new))
    bad = []
    if set(po) != set(pn) or new.get("_about") != old.get("_about"): bad.append("項目の増減")
    for k, o in po.items():
        n = pn.get(k)
        if n is None: continue
        if {kk: vv for kk, vv in n.items() if kk != "value"} != {kk: vv for kk, vv in o.items() if kk != "value"}: bad.append(f"{'.'.join(k)} の範囲が変わった")
        if n["value"] == o["value"]: continue
        if "choices" in o:
            if n["value"] not in o["choices"]: bad.append(f"{'.'.join(k)}={n['value']} は choices に無い")
        elif not (isinstance(n["value"], int) and o["min"] <= n["value"] <= o["max"] and abs(n["value"] - o["value"]) <= o["step"]):
            bad.append(f"{'.'.join(k)}: {o['value']}→{n['value']} は範囲か step を超える")
        res["changes"].append(f"{'.'.join(k)}: {o['value']} → {n['value']}")
    cl = lambda p: sum(v["value"] for k, v in p.items() if k[:2] == ("edition", "category_limits"))
    if cl(po) != cl(pn): bad.append(f"カテゴリの合計本数が変わった（{cl(po)}→{cl(pn)}）")
    add = open(f"{job}/changelog_add.md", encoding="utf-8").read().strip() if os.path.exists(f"{job}/changelog_add.md") else ""
    add = "\n".join(l for l in add.splitlines() if re.match(r"^\d{4}-\d\d-\d\d \| .+ \| .+ \| .+", l))
    if res["changes"] and not add: bad.append("changelog の行が無い")
    if bad:
        res["params"] = "rejected"; res["problems"] += bad; res["changes"] = []
    elif res["changes"]:
        res["params"] = "changed"
        open(f"{out}/params.json", "w", encoding="utf-8").write(json.dumps(new, ensure_ascii=False, indent=1))
        open(f"{out}/changelog_add.md", "w", encoding="utf-8").write(add + "\n")
    json.dump(res, open(f"{out}/check.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    c, *a = sys.argv[1:]
    {"prep": cmd_prep, "check": cmd_check}[c](*a)
