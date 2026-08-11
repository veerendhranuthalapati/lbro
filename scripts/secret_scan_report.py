"""Repository secret scan — reports FOUND/NOT FOUND only, never prints values."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {
    ".git", "node_modules", "dist", "__pycache__", ".pytest_cache",
    "frontend/dist", "ml/models",
}
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS_ACCESS_KEY_ID", re.compile(r"AWS_ACCESS_KEY_ID\s*=\s*\S+", re.I)),
    ("AWS_SECRET_ACCESS_KEY", re.compile(r"AWS_SECRET_ACCESS_KEY\s*=\s*\S+", re.I)),
    ("SECRET_KEY", re.compile(r"SECRET_KEY\s*=\s*\S+", re.I)),
    ("POSTGRES_PASSWORD", re.compile(r"POSTGRES_PASSWORD\s*=\s*\S+", re.I)),
    ("JWT secret", re.compile(r"JWT[_-]?SECRET\s*=\s*\S+", re.I)),
    ("Private key PEM", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("Database URL with password", re.compile(r"postgresql(?:\+asyncpg)?://[^:]+:[^@]+@", re.I)),
]
SKIP_VALUE = re.compile(
    r"(REPLACE_|change-me|EXAMPLE|your-|not-for-production|test-secret|__LBRO_|dev-only-lbro|\$\{|<)",
    re.I,
)
SKIP_FILES = {".env.prod.example", ".env.example", "backend/.env.example"}


def scan_working_tree() -> list[tuple[str, str, str]]:
    findings: list[tuple[str, str, str]] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith((".png", ".jpg", ".pyc", ".woff", ".woff2", ".ico", ".pdf", ".bundle")):
                continue
            path = Path(dirpath) / fn
            rel = path.relative_to(ROOT).as_posix()
            if rel in SKIP_FILES or rel.endswith(".patch"):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                for ctype, pat in PATTERNS:
                    m = pat.search(line)
                    if not m:
                        continue
                    if SKIP_VALUE.search(m.group(0)):
                        continue
                    if ctype == "SECRET_KEY" and ("tests/" in rel or "conftest" in rel):
                        continue
                    findings.append((rel, str(i), ctype))
    return findings


def git_paths_in_history(ref: str = "--all") -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(ROOT), "log", ref, "--name-only", "--pretty=format:", "--", ".env.prod"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]


def git_commits_for_path(ref: str) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(ROOT), "log", ref, "--oneline", "--", ".env.prod"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]


def git_objects_env_prod() -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(ROOT), "rev-list", "--objects", "--all"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [ln for ln in out.stdout.splitlines() if ln.endswith(" .env.prod")]


def main() -> None:
    print("=== WORKING TREE ===")
    wt = scan_working_tree()
    if wt:
        for rel, line, ctype in sorted(set(wt)):
            print(f"FOUND|{ctype}|{rel}:{line}")
    else:
        print("NOT FOUND|working tree|no live credential assignment patterns")

    print("\n=== LOCAL MAIN HISTORY (.env.prod) ===")
    commits = git_commits_for_path("main")
    if commits:
        for c in commits:
            print(f"FOUND|.env.prod file|commit {c.split()[0]}")
    else:
        print("NOT FOUND|local main history|.env.prod")

    print("\n=== ALL LOCAL REFS HISTORY (.env.prod) ===")
    commits_all = git_commits_for_path("--all")
    if commits_all:
        for c in commits_all:
            print(f"FOUND|.env.prod file|commit {c.split()[0]}")
    else:
        print("NOT FOUND|all local refs|.env.prod")

    print("\n=== ORIGIN/MAIN HISTORY (.env.prod) — remote still exposed until force-push ===")
    commits_remote = git_commits_for_path("origin/main")
    if commits_remote:
        for c in commits_remote:
            print(f"FOUND|.env.prod file|origin/main commit {c.split()[0]}")
    else:
        print("NOT FOUND|origin/main|.env.prod")

    print("\n=== GIT OBJECTS (.env.prod path) ===")
    objs = git_objects_env_prod()
    if objs:
        for o in objs:
            print(f"FOUND|.env.prod blob|object {o.split()[0]}")
    else:
        print("NOT FOUND|git objects|.env.prod")

    print("\n=== TRACKED ENV FILES ===")
    tracked = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files"],
        capture_output=True,
        text=True,
        check=False,
    )
    env_files = [ln for ln in tracked.stdout.splitlines() if ".env" in ln.lower()]
    for f in env_files:
        kind = "placeholder example" if "example" in f or "mock" in f else "env file"
        print(f"FOUND|{kind}|tracked {f}")


if __name__ == "__main__":
    main()
