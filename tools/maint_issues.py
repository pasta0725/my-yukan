"""Helpers for codex-fix-issues.yml (2026-11-14, the user's request: move the twice-daily 「AI報告の確認と修正」 from Claude to
Codex to save Claude usage, quality must not drop). Runs on GitHub Actions. Never prints or reads secrets.

  python3 tools/maint_issues.py list <out dir> <state.json>
      open issues labeled AIからの報告 -> <out dir>/issues/<n>.md (body + comments, as data) and <out dir>/todo.json.
      An issue is skipped when it is on hold (body or a comment says 保留 / ユーザー待ち) and nothing new came after the last
      hold mark (and after the last time this job looked at it, state.json). Prints todo=<n,n,...> (empty: nothing to do).
  python3 tools/maint_issues.py guard <repo copy> <base sha> <todo.json> <out dir>
      after Codex: builds the patch, applies the safety limits, re-runs the checks, and writes <out dir>/patch.diff and
      <out dir>/decisions.json. If any limit or check fails, every "fixed"/"partial" becomes "hold" and no patch is written.
      decisions: fixed (pushed, closed), partial (pushed, stays open with 保留), hold, keep (no comment), none.
  python3 tools/maint_issues.py report <decisions.json or -> <todo.json or -> <run url> <commit or -> <out.md>
      the Japanese report: first line RESULT: ..., then one line per issue.
  python3 tools/maint_issues.py seen <state.json> <decisions.json>
      remembers when each held issue was last looked at.
"""
import datetime, json, os, re, subprocess, sys

REPO = os.environ.get("GITHUB_REPOSITORY", "pasta0725/my-yukan")
LABEL = "AIからの報告"
HOLD = re.compile(r"保留|ユーザー待ち")
MAX_LINES, MAX_FILES = 200, 10
# never changed by the automatic fix (secrets handling, the Codex setup, this job itself)
FORBIDDEN = re.compile(r"^(\.github/actions/|\.github/workflows/codex-fix-issues\.yml$|tools/maint_issues\.py$|tools/codex/fix_issues\.md$|\.gitignore$)")
SECRETISH = re.compile(r"secrets\.|CODEX_AUTH|GITHUB_TOKEN|github\.token|x-access-token|GH_TOKEN|auth\.json|REFRESH_TOKEN|API_KEY|PASSWORD", re.I)
SCRATCH = ("_fix/", "fix_issues.md", "codex.log", "last.txt")


def ts(s): return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def gh(path, *args):
    out = subprocess.run(["gh", "api", "-X", "GET", path, *args], capture_output=True, text=True, check=True).stdout
    return json.loads(out) if out.strip() else []


def cmd_list(out, state_path):
    state = json.load(open(state_path)) if os.path.exists(state_path) else {}
    seen = state.get("seen", {})
    issues = gh(f"repos/{REPO}/issues", "-f", f"labels={LABEL}", "-f", "state=open", "-f", "per_page=50")
    os.makedirs(f"{out}/issues", exist_ok=True)
    todo = []
    for it in issues:
        if "pull_request" in it: continue
        n = it["number"]
        comments = gh(f"repos/{REPO}/issues/{n}/comments", "-f", "per_page=100")
        marks = [ts(it["created_at"])] if HOLD.search(it.get("body") or "") else []
        marks += [ts(c["created_at"]) for c in comments if HOLD.search(c.get("body") or "")]
        upd = ts(it["updated_at"])
        last_hold = max(marks) if marks else None
        last_seen = ts(seen[str(n)]) if str(n) in seen else None
        newer = [x for x in (last_hold, last_seen) if x]
        if newer and upd <= max(newer) + datetime.timedelta(minutes=5):
            print(f"skip #{n} (on hold / already seen, no update)"); continue
        new_after = max(newer) if newer else None
        lines = [f"# Issue #{n}: {it['title']}", f"作成 {it['created_at']} / 更新 {it['updated_at']}",
                 f"状態: {'保留中（この印より後のコメントが新しい情報）' if last_hold else '新しい報告'}", "", "## 本文", it.get("body") or ""]
        for c in comments:
            tag = " 【新しい】" if new_after and ts(c["created_at"]) > new_after else ""
            lines += ["", f"## コメント {c['created_at']}{tag}", c.get("body") or ""]
        open(f"{out}/issues/{n}.md", "w", encoding="utf-8").write("\n".join(lines) + "\n")
        todo.append({"number": n, "title": it["title"], "on_hold": bool(last_hold), "updated_at": it["updated_at"]})
    json.dump(todo, open(f"{out}/todo.json", "w"), ensure_ascii=False, indent=1)
    print("todo=" + ",".join(str(t["number"]) for t in todo))


def sh(cmd, cwd, timeout=180):
    p = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    return p.returncode, (p.stdout + p.stderr)[-1500:]


def cmd_guard(repo, base, todo_path, out):
    os.makedirs(out, exist_ok=True)
    todo = {t["number"]: t for t in json.load(open(todo_path))}
    try: res = json.load(open(os.path.join(repo, "_fix", "result.json")))
    except Exception as e: res = {"issues": [], "checks": [], "error": f"result.json を読めない（{type(e).__name__}）"}
    checks = [c for c in res.get("checks", []) if isinstance(c, str)][:8]
    dec = {}
    for r in res.get("issues", []):
        try: n = int(r.get("number"))
        except Exception: continue
        if n not in todo: continue
        d = r.get("decision") if r.get("decision") in ("fixed", "partial", "hold", "keep") else "hold"
        if d == "keep" and not todo[n]["on_hold"]: d = "hold"
        dec[n] = {"number": n, "title": todo[n]["title"], "decision": d,
                  "comment": str(r.get("comment") or "").strip()[:3000], "summary": str(r.get("summary") or "").strip()[:200]}
    for n, t in todo.items():
        if n not in dec: dec[n] = {"number": n, "title": t["title"], "decision": "none", "comment": "", "summary": "Codex の結果が出なかった（次回もう一度見る）"}
    # the patch: everything Codex changed (even if it committed), minus its scratch files
    for s in SCRATCH: sh(["rm", "-rf", s], repo)
    sh(["git", "add", "-A"], repo)
    _, names = sh(["git", "diff", "--cached", "--name-status", base], repo)
    _, numstat = sh(["git", "diff", "--cached", "--numstat", base], repo)
    patch = subprocess.run(["git", "diff", "--cached", "--binary", base], cwd=repo, capture_output=True, text=True).stdout
    problems = []
    files = [l.split("\t") for l in names.strip().splitlines() if l.strip()]
    total = 0
    for row in numstat.strip().splitlines():
        a, d, f = (row.split("\t") + ["", "", ""])[:3]
        if a == "-": problems.append(f"画像などの変更 {f}")
        else: total += int(a) + int(d)
    for st, *paths in files:
        if st.startswith("D"): problems.append(f"ファイルの削除 {paths[0]}")
        if st.startswith("R"): problems.append(f"ファイル名の変更 {paths[0]}")
        for p in paths:
            if FORBIDDEN.search(p): problems.append(f"触ってはいけないファイル {p}")
    if total > MAX_LINES: problems.append(f"変更が大きすぎる（{total}行 > {MAX_LINES}行）")
    if len(files) > MAX_FILES: problems.append(f"ファイルが多すぎる（{len(files)}個）")
    changed_lines = [l for l in patch.splitlines() if l[:1] in "+-" and not l.startswith(("+++", "---"))]
    if any(SECRETISH.search(l) for l in changed_lines): problems.append("鍵・トークンの扱いに関わる行の変更")
    fixed = [d for d in dec.values() if d["decision"] in ("fixed", "partial")]
    if files and not fixed: problems.append("直した件が無いのにファイルが変わっている")
    # checks: python compile, workflow YAML, JSON, and the commands Codex used to verify its fix
    log = []
    if files and not problems:
        import yaml
        for st, *paths in files:
            p = os.path.join(repo, paths[-1])
            try:
                if p.endswith(".py"):
                    rc, o = sh(["python3", "-m", "py_compile", p], repo)
                    if rc: raise RuntimeError(o)
                elif p.endswith((".yml", ".yaml")):
                    y = yaml.safe_load(open(p, encoding="utf-8"))
                    if "/workflows/" in p and not (isinstance(y, dict) and "jobs" in y and (True in y or "on" in y)): raise RuntimeError("on/jobs が無い")
                elif p.endswith(".json"):
                    json.load(open(p, encoding="utf-8"))
                log.append(f"ok {paths[-1]}")
            except Exception as e:
                problems.append(f"確認に失敗 {paths[-1]}：{str(e)[:200]}")
        for c in checks:
            try: rc, o = sh(c, repo, timeout=180)
            except subprocess.TimeoutExpired: rc, o = "timeout", ""
            log.append(f"$ {c} -> {rc}")
            if rc != 0: problems.append(f"確かめのコマンドが失敗：{c[:120]}（{rc}）")
        sh(["git", "add", "-A"], repo)
        after = subprocess.run(["git", "diff", "--cached", "--binary", base], cwd=repo, capture_output=True, text=True).stdout
        if after != patch: problems.append("確かめのコマンドがファイルを変えた（生成物が残った）")
    if problems:
        for d in fixed:
            d["decision"] = "hold"
            d["comment"] = ("保留：自動の安全確認で止めました（" + "／".join(problems[:3]) + "）。下の直し案は main に反映していません：\n\n" + d["comment"])[:3000]
            d["summary"] = "自動の安全確認で止めた：" + problems[0]
        patch = ""
    for d in dec.values():  # a hold / partial comment always starts with 保留： so the next run skips it
        if d["decision"] in ("hold", "partial") and not d["comment"].startswith("保留"): d["comment"] = "保留：" + d["comment"]
    open(os.path.join(out, "patch.diff"), "w", encoding="utf-8").write(patch)
    json.dump({"decisions": sorted(dec.values(), key=lambda x: x["number"]), "problems": problems, "lines": total,
               "files": [p[-1] for _, *p in files], "checks": log, "codex_error": res.get("error", "")},
              open(os.path.join(out, "decisions.json"), "w"), ensure_ascii=False, indent=1)
    print(f"files={len(files)} lines={total} problems={problems}")


def cmd_report(dec_path, todo_path, url, commit, out):
    lines = []
    if todo_path != "-" and os.path.exists(todo_path) and not json.load(open(todo_path)):
        lines = ["RESULT: NONE", "新しい報告はありません。"]
    elif dec_path == "-" or not os.path.exists(dec_path):
        lines = ["RESULT: ERROR", "Codex の作業が途中で止まりました（何も変えていません）。"]
    else:
        D = json.load(open(dec_path))["decisions"]
        c = {k: sum(1 for d in D if d["decision"] == k) for k in ("fixed", "partial", "hold", "keep", "none")}
        lines = [f"RESULT: FIXED={c['fixed']} PARTIAL={c['partial']} HOLD={c['hold']} KEEP={c['keep']} NONE={c['none']}" + (f" COMMIT={commit}" if commit != "-" else "")]
        word = {"fixed": "直した", "partial": "一部直した（残りは保留）", "hold": "保留", "keep": "保留のまま", "none": "未処理"}
        for d in D: lines.append(f"#{d['number']} {word[d['decision']]}：{d['summary'] or d['title']}")
    lines.append(f"実行：{url}")
    open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))


def cmd_seen(state_path, dec_path):
    """after commenting: remember when each held issue was last looked at (so an unchanged one is not read again)."""
    state = json.load(open(state_path)) if os.path.exists(state_path) else {}
    seen = state.setdefault("seen", {})
    for d in json.load(open(dec_path))["decisions"]:
        if d["decision"] in ("hold", "keep", "partial"):
            seen[str(d["number"])] = gh(f"repos/{REPO}/issues/{d['number']}")["updated_at"]
    json.dump(state, open(state_path, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    c, *a = sys.argv[1:]
    {"list": cmd_list, "guard": cmd_guard, "report": cmd_report, "seen": cmd_seen}[c](*a)
