"""Run `codex exec` once per job folder, a few at a time (2026-11-14, the user's request: move work from Claude to Codex).
Used by codex-fill.yml, codex-factcheck.yml, official-images.yml (codex_pick) and codex-write.yml. Runs on GitHub Actions.

usage: python3 tools/codex_run.py <task.md> <jobs dir> [--files f1,f2] [--parallel 2] [--timeout 600]
                                  [--model gpt-6-astra] [--effort high] [--image story.jpg] [--search]
  every direct sub folder of <jobs dir> that holds a file is one job: <task.md> (and --files) are copied into it, then
  codex runs inside that folder (workspace-write sandbox: it can only write there; no internet unless --search).
  The model and reasoning effort are always set explicitly. If the model is refused, the job is retried once with
  the account's default model (written to the log and the job summary).
  Logs: <job>/codex.log. The job summary ($GITHUB_STEP_SUMMARY) gets the model really used and the seconds per job.
"""
import argparse, concurrent.futures as cf, os, re, shutil, subprocess, sys, time

ap = argparse.ArgumentParser()
ap.add_argument("task"); ap.add_argument("jobs")
ap.add_argument("--files", default=""); ap.add_argument("--parallel", type=int, default=2)
ap.add_argument("--timeout", type=int, default=600); ap.add_argument("--model", default="gpt-6-astra")
ap.add_argument("--effort", default="high"); ap.add_argument("--image", default=""); ap.add_argument("--search", action="store_true")
a = ap.parse_args()

jobs = sorted(os.path.join(a.jobs, d) for d in os.listdir(a.jobs) if os.path.isdir(os.path.join(a.jobs, d))
              and any(os.path.isfile(os.path.join(a.jobs, d, f)) for f in os.listdir(os.path.join(a.jobs, d))))
prompt = open(a.task, encoding="utf-8").read()


def run(d):
    for f in [a.task] + [x for x in a.files.split(",") if x]: shutil.copy(f, d)
    base = ["codex"] + (["--search"] if a.search else []) + ["exec", "--skip-git-repo-check", "-s", "workspace-write", "-C", d,
                                                             "-c", f'model_reasoning_effort="{a.effort}"', "-o", os.path.join(d, "last.txt")]
    img = ["-i", os.path.join(d, a.image)] if a.image and os.path.exists(os.path.join(d, a.image)) else []
    t0, note = time.time(), ""
    for attempt, model in enumerate([a.model, None] if a.model else [None]):
        cmd = base + (["-m", model] if model else []) + img + ["--", prompt]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=a.timeout, stdin=subprocess.DEVNULL)
            log, rc = p.stdout + "\n" + p.stderr, p.returncode
        except subprocess.TimeoutExpired as e:
            log, rc = (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else str(e.stdout or ""), "timeout"
        open(os.path.join(d, "codex.log"), "a", encoding="utf-8").write(f"--- attempt {attempt} model={model} rc={rc}\n{log[-6000:]}\n")
        used = (re.findall(r"(?m)^model:\s*(\S+)", log) or [model or "?"])[0]
        eff = (re.findall(r"(?m)^reasoning effort:\s*(\S+)", log) or [a.effort])[0]
        refused = rc not in (0, "timeout") and re.search(r"model.{0,80}(not (supported|found|available|exist)|unsupported|invalid|does not have access)", log, re.I | re.S)
        if refused and model:
            note = f"model {model} refused; retried with the default model"; continue
        return d, used, eff, rc, round(time.time() - t0), note
    return d, "?", a.effort, "refused", round(time.time() - t0), note


with cf.ThreadPoolExecutor(max(1, a.parallel)) as ex:
    res = list(ex.map(run, jobs))
lines = [f"| {os.path.basename(d)} | {m} | {e} | {rc} | {s}s | {n} |" for d, m, e, rc, s, n in res]
print("\n".join(lines))
models = sorted({r[1] for r in res})
summ = os.environ.get("GITHUB_STEP_SUMMARY")
if summ:
    with open(summ, "a", encoding="utf-8") as f:
        f.write(f"\n### codex_run {os.path.basename(a.task)}: model used {', '.join(models) or '-'} / effort {a.effort} (asked: {a.model})\n\n"
                "| job | model | effort | exit | time | note |\n|---|---|---|---|---|---|\n" + "\n".join(lines) + "\n")
