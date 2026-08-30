#!/usr/bin/env python3
from __future__ import annotations
import os
import shutil
import subprocess
import sys


def run(args):
    p = subprocess.run(args, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p


def main():
    assert os.name == "nt", "Windows required"
    codex = shutil.which("codex")
    assert codex, "codex missing after npm install"
    version = run([codex, "--version"])
    assert version.returncode == 0, version.stderr
    print("CODEX_VERSION", (version.stdout + version.stderr).strip())

    json_flag = None
    for flag in ("--json", "--experimental-json"):
        p = run([codex, "exec", flag, "--help"])
        if p.returncode == 0:
            json_flag = flag
            break
    assert json_flag, "No JSON event flag accepted"

    base = [json_flag]
    if run([codex, "exec", json_flag, "--ephemeral", "--help"]).returncode == 0:
        base.append("--ephemeral")

    profiles = [
        ("explicit-after-long", [], ["--sandbox", "workspace-write", "--ask-for-approval", "never"]),
        ("explicit-after-short-approval", [], ["--sandbox", "workspace-write", "-a", "never"]),
        ("explicit-before-long", ["--sandbox", "workspace-write", "--ask-for-approval", "never"], []),
        ("explicit-before-short", ["-s", "workspace-write", "-a", "never"], []),
        ("config-approval-after", [], ["--sandbox", "workspace-write", "-c", 'approval_policy="never"']),
        ("config-approval-before", ["--sandbox", "workspace-write", "-c", 'approval_policy="never"'], []),
        ("config-both-before", ["-c", 'sandbox_mode="workspace-write"', "-c", 'approval_policy="never"'], []),
        ("config-both-after", [], ["-c", 'sandbox_mode="workspace-write"', "-c", 'approval_policy="never"']),
        ("legacy-full-auto-after", [], ["--full-auto"]),
        ("legacy-full-auto-before", ["--full-auto"], []),
    ]
    selected = None
    for name, pre, post in profiles:
        p = run([codex, *pre, "exec", *base, *post, "--help"])
        print(name, "rc=", p.returncode)
        if p.returncode == 0:
            selected = name
            break
    assert selected, "No safe non-interactive workspace-write parser profile accepted"
    print("REAL_CODEX_CLI_PROFILE_PASS", selected)


if __name__ == "__main__":
    main()
