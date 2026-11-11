"""Keep a Short's sounds, pictures and clips on the throwaway branch "work", not on main (user's decision 2026-11-12).
Everything on main stays in GitHub's history forever (about 18MB a day of narration, images and clips added up);
"work" is deleted after the video is published and moved to Google Drive (drive-store.yml), so its files leave GitHub.

  python3 tools/work_branch.py put <path> [<path> ...]   copy these files/folders from the working tree to "work" (same paths) and push
  python3 tools/work_branch.py get <path> [<path> ...]   copy these paths from "work" into the working tree (not staged, never committed to main)
  python3 tools/work_branch.py ls [<path>]                list what "work" holds

Run it inside a clone of pasta0725/my-yukan. main's .gitignore keeps these files out of main, so a plain `git add` cannot put them back there.
Nothing is printed about keys. Text (scripts, spec.json, short.html, lines.json, urls.txt) stays on main as before."""
import os, shutil, subprocess, sys, tempfile

B = "work"


def git(*a, cwd=None, check=True, quiet=False):
    r = subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        raise SystemExit(f"git {' '.join(a)} failed: {r.stderr.strip()[:300]}")
    return r.stdout


def fetch():
    return subprocess.run(["git", "fetch", "-q", "origin", f"+{B}:refs/remotes/origin/{B}"], capture_output=True).returncode == 0


def put(paths):
    top = git("rev-parse", "--show-toplevel").strip()
    paths = [os.path.relpath(os.path.abspath(p), top) for p in paths]
    for attempt in range(5):
        have = fetch()
        tmp = tempfile.mkdtemp(prefix="work-")
        try:
            if have:
                git("worktree", "add", "-q", "--detach", tmp, f"origin/{B}", cwd=top)
            else:
                git("worktree", "add", "-q", "--detach", tmp, cwd=top)
                git("checkout", "-q", "--orphan", "tmp-work", cwd=tmp)
                git("rm", "-rq", "--cached", ".", cwd=tmp, check=False)
                for x in os.listdir(tmp):
                    if x != ".git": (shutil.rmtree if os.path.isdir(os.path.join(tmp, x)) else os.remove)(os.path.join(tmp, x))
            for p in paths:
                src, dst = os.path.join(top, p), os.path.join(tmp, p)
                if os.path.isdir(src): shutil.copytree(src, dst, dirs_exist_ok=True)
                else: os.makedirs(os.path.dirname(dst) or ".", exist_ok=True); shutil.copy2(src, dst)
                git("add", "-f", "--", p, cwd=tmp)
            if not git("status", "--porcelain", cwd=tmp).strip():
                print("work: nothing new"); return
            git("-c", "user.name=pasta0725", "-c", "user.email=pasta0725@users.noreply.github.com", "commit", "-qm", "素材：" + " ".join(paths)[:200], cwd=tmp)
            if subprocess.run(["git", "push", "-q", "origin", f"HEAD:refs/heads/{B}"], cwd=tmp, capture_output=True).returncode == 0:
                print("work: saved", " ".join(paths)); return
            print(f"work: push failed ({attempt + 1}), retrying")
        finally:
            git("worktree", "remove", "--force", tmp, cwd=top, check=False)
            subprocess.run(["git", "branch", "-D", "tmp-work"], cwd=top, capture_output=True)
    raise SystemExit("work: could not push")


def get(paths):
    if not fetch(): print("work: the branch does not exist yet"); sys.exit(1)
    top = git("rev-parse", "--show-toplevel").strip()
    paths = [os.path.relpath(os.path.abspath(p), top) for p in paths]
    files = git("ls-tree", "-r", "--name-only", f"origin/{B}", "--", *paths, cwd=top).split()
    for f in files:
        data = subprocess.run(["git", "show", f"origin/{B}:{f}"], cwd=top, capture_output=True).stdout
        os.makedirs(os.path.dirname(os.path.join(top, f)) or ".", exist_ok=True)
        open(os.path.join(top, f), "wb").write(data)
    print(f"work: got {len(files)} files")


if __name__ == "__main__":
    cmd, rest = sys.argv[1] if len(sys.argv) > 1 else "", sys.argv[2:]
    if cmd == "put" and rest: put(rest)
    elif cmd == "get" and rest: get(rest)
    elif cmd == "ls":
        if fetch(): print(git("ls-tree", "-r", "--name-only", f"origin/{B}", "--", *rest))
        else: print("work: the branch does not exist yet")
    else: print(__doc__); sys.exit(2)
