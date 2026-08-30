#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from datetime import datetime, timezone

PACKAGE_ID = "PHASE24_25_FINAL_RESOLVER_R3"
PACKAGE_DIR = Path(__file__).resolve().parent
BLUEPRINT_SHA = "29dcc194f1e1f4a7300c302627cb6f2510f9ac8b"
PREOS_SHA = "daf15830ccf84c75dfe4b23a62130b52685c65a0"
GSTACK_SHA = "a557942f6cd5119ce956dcd3f66312234bd5dba8"
SOURCE_COMMITS = {"blueprint": BLUEPRINT_SHA, "preos": PREOS_SHA, "gstack": GSTACK_SHA}
SOURCE_SPECS = {
    "wed_dev_skill": ("blueprint", "https://github.com/WilsonMisor/wed_dev_skill.git", BLUEPRINT_SHA),
    "PREOS": ("preos", "https://github.com/WilsonMisor/PREOS.git", PREOS_SHA),
    "gstack": ("gstack", "https://github.com/WilsonMisor/gstack.git", GSTACK_SHA),
}
PREOS_SKILLS = [
    "preos", "preos-project-init", "preos-risk-model", "preos-architecture-economics",
    "preos-production-plan", "preos-production-implement", "preos-production-learn",
]
REQUIRED_SKILLS = [
    "ai-product-delivery-blueprint",
    *PREOS_SKILLS,
    "gstack-preos-handoff", "gstack-context-restore", "gstack-review", "gstack-cso",
    "gstack-qa", "gstack-benchmark", "gstack-ship", "gstack-land-and-deploy", "gstack-canary",
]
BLOCKED_PROCESS_NAMES = {
    "claude.exe", "gemini.exe", "kiro.exe", "droid.exe", "opencode.exe",
    "claude", "gemini", "kiro", "droid", "opencode",
}


class AcceptanceFailure(RuntimeError):
    def __init__(self, verdict: str, failure_class: str, stage: str, detail: str, *, extra: str = ""):
        super().__init__(detail)
        self.verdict = verdict
        self.failure_class = failure_class
        self.stage = stage
        self.detail = detail
        self.extra = extra


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def cmdtext(cmd) -> str:
    return subprocess.list2cmdline([str(x) for x in cmd])


def run(cmd, *, cwd=None, env=None, timeout=1200, stdin_text=None):
    """Run a subprocess with a total text-output contract.

    CompletedProcess permits stdout/stderr to be None in some invocation shapes.
    The acceptance harness normalizes both to strings before any downstream use.
    """
    p = subprocess.run(
        [str(x) for x in cmd], cwd=str(cwd) if cwd else None, env=env,
        input=stdin_text, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return subprocess.CompletedProcess(
        p.args, p.returncode,
        "" if p.stdout is None else str(p.stdout),
        "" if p.stderr is None else str(p.stderr),
    )


def require_success(cmd, *, cwd=None, env=None, timeout=1200, failure_class="HARNESS_OR_INSTALLATION", stage="COMMAND"):
    p = run(cmd, cwd=cwd, env=env, timeout=timeout)
    if p.returncode != 0:
        raise AcceptanceFailure(
            "PHASE_24_FAIL_SKILL_DISCOVERY", failure_class, stage,
            f"Command failed with exit code {p.returncode}: {cmdtext(cmd)}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}",
        )
    return p


def excerpt(text: str, limit=12000) -> str:
    text = str(text or "")
    if len(text) <= limit:
        return text
    return "... [truncated] ...\n" + text[-limit:]


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")).resolve()


def read_skill_name(skill_file: Path) -> str | None:
    if not skill_file.is_file():
        return None
    for line in skill_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip().startswith("name:"):
            return line.split(":", 1)[1].strip().strip('"\'')
    return None


def copy_tree(src: Path, dst: Path, *, exclude_git=True) -> None:
    if dst.exists() or dst.is_symlink():
        if dst.is_dir() and not dst.is_symlink():
            shutil.rmtree(dst)
        else:
            dst.unlink()
    ignore = shutil.ignore_patterns(".git") if exclude_git else None
    shutil.copytree(src, dst, symlinks=False, ignore=ignore)


def framework_related(name: str) -> bool:
    return (
        name in {"ai-web-delivery-blueprint", "ai-product-delivery-blueprint", "preos", "gstack", "connect-chrome"}
        or name.startswith("preos-") or name.startswith("gstack-")
    )


def list_processes() -> dict[int, str]:
    if os.name != "nt":
        return {}
    p = subprocess.run(["tasklist.exe", "/FO", "CSV", "/NH"], text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    result = {}
    if p.returncode == 0:
        for row in csv.reader(io.StringIO(p.stdout or "")):
            if len(row) >= 2:
                try:
                    result[int(row[1])] = row[0].lower()
                except ValueError:
                    pass
    return result


class ProviderMonitor:
    def __init__(self):
        self.baseline = list_processes()
        self.violations: list[tuple[int, str]] = []
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        if os.name == "nt":
            self.thread = threading.Thread(target=self._watch, daemon=True)
            self.thread.start()

    def _watch(self):
        while not self.stop_event.wait(0.25):
            for pid, name in list_processes().items():
                if pid not in self.baseline and name in BLOCKED_PROCESS_NAMES and (pid, name) not in self.violations:
                    self.violations.append((pid, name))
                    subprocess.run(["taskkill.exe", "/PID", str(pid), "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)


def external_failure(text: str) -> bool:
    t = text.lower()
    return any(x in t for x in (
        "usage limit", "rate limit", "try again at", "service unavailable", "temporarily unavailable",
        "connection error", "network error", "authentication required", "not logged in", "login required",
        "http 429", "too many requests", "timed out connecting", "failed to connect",
    ))


def find_git_bash(git: str) -> Path:
    candidates = []
    if os.name == "nt":
        p = run(["where.exe", "bash.exe"], timeout=60)
        if p.returncode == 0:
            candidates.extend(Path(x.strip()) for x in p.stdout.splitlines() if x.strip())
        gp = Path(git).resolve()
        candidates.extend([
            gp.parents[1] / "bin" / "bash.exe" if len(gp.parents) > 1 else gp,
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe",
        ])
    else:
        b = shutil.which("bash")
        if b:
            candidates.append(Path(b))
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise AcceptanceFailure("PHASE_24_FAIL_SKILL_DISCOVERY", "ENVIRONMENT", "ENVIRONMENT_PREFLIGHT",
                            "Git Bash was not found.")


def remote_head(git: str, name: str, url: str, expected: str, log_lines: list[str]) -> str:
    last = None
    for attempt in range(1, 4):
        p = run([git, "ls-remote", url, "refs/heads/main"], timeout=120)
        last = p
        log_lines.append(f"{name} ls-remote attempt {attempt}: rc={p.returncode}\n{p.stdout}{p.stderr}")
        if p.returncode == 0 and p.stdout.strip():
            sha = p.stdout.split()[0].strip().lower()
            if sha != expected.lower():
                raise AcceptanceFailure("PHASE_24_FAIL_SOURCE_IDENTITY", "SOURCE_IDENTITY", "REMOTE_SOURCE_IDENTITY_PREFLIGHT",
                                        f"{name} main moved. Expected {expected}, observed {sha}.")
            return sha
        time.sleep(attempt)
    detail = (last.stdout + "\n" + last.stderr) if last else "no output"
    verdict = "PHASE_25_BLOCKED_EXTERNAL_SERVICE" if external_failure(detail) else "PHASE_24_FAIL_SKILL_DISCOVERY"
    raise AcceptanceFailure(verdict, "NETWORK_OR_GIT", "REMOTE_SOURCE_IDENTITY_PREFLIGHT",
                            f"Could not resolve {name} main after retries.\n{detail}")


def checkout_exact_source(git: str, name: str, url: str, expected: str, root: Path, log_lines: list[str]) -> Path:
    dest = root / name
    require_success([git, "init", str(dest)], stage="PREPARE_EXACT_SOURCES")
    require_success([git, "-C", dest, "config", "core.autocrlf", "false"], stage="PREPARE_EXACT_SOURCES")
    require_success([git, "-C", dest, "config", "core.eol", "lf"], stage="PREPARE_EXACT_SOURCES")
    require_success([git, "-C", dest, "remote", "add", "origin", url], stage="PREPARE_EXACT_SOURCES")
    last = None
    for attempt in range(1, 4):
        p = run([git, "-c", "http.version=HTTP/1.1", "-C", dest, "fetch", "--depth", "1", "--no-tags",
                 "origin", expected], timeout=300)
        last = p
        log_lines.append(f"{name} fetch attempt {attempt}: rc={p.returncode}\n{p.stdout}{p.stderr}")
        if p.returncode == 0:
            break
        time.sleep(attempt * 2)
    else:
        raise AcceptanceFailure("PHASE_24_FAIL_SKILL_DISCOVERY", "NETWORK_OR_GIT", "PREPARE_EXACT_SOURCES",
                                f"{name} could not be fetched after retries.\n{last.stderr if last else ''}")
    require_success([git, "-C", dest, "checkout", "--detach", expected], stage="PREPARE_EXACT_SOURCES")
    p = require_success([git, "-C", dest, "rev-parse", "HEAD"], stage="PREPARE_EXACT_SOURCES")
    observed = p.stdout.strip().lower()
    if observed != expected.lower():
        raise AcceptanceFailure("PHASE_24_FAIL_SOURCE_IDENTITY", "SOURCE_IDENTITY", "PREPARE_EXACT_SOURCES",
                                f"{name} checkout mismatch: expected {expected}, observed {observed}")
    return dest


def run_preos_validation(preos: Path, report_dir: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(preos / "scripts")
    commands = [
        [sys.executable, str(preos / "scripts" / "validate-preos.py")],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
    ]
    chunks = []
    for cmd in commands:
        p = run(cmd, cwd=preos, env=env, timeout=1200)
        chunks.append("COMMAND\n" + cmdtext(cmd) + f"\nEXIT CODE\n{p.returncode}\nSTDOUT\n{p.stdout}\nSTDERR\n{p.stderr}\n")
        if p.returncode != 0:
            (report_dir / "preos-local-validation.log").write_text("\n\n".join(chunks), encoding="utf-8")
            raise AcceptanceFailure("PHASE_24_FAIL_SKILL_DISCOVERY", "PREOS_WINDOWS_VALIDATION", "PREOS_LOCAL_VALIDATION",
                                    "PREOS Windows validation failed before skill mutation.\n" + excerpt(p.stdout + "\n" + p.stderr))
    (report_dir / "preos-local-validation.log").write_text("\n\n".join(chunks), encoding="utf-8")


def deterministic_recovery_preflight(preos: Path, report_dir: Path, git: str) -> None:
    base = Path(tempfile.mkdtemp(prefix="preos-recovery-preflight-"))
    repo = base / "repo"; repo.mkdir()
    state = base / "state"
    env = os.environ.copy(); env["PREOS_STATE_ROOT"] = str(state); env["PYTHONPATH"] = str(preos / "scripts")
    log = []
    def rr(cmd, *, check=True):
        p = run(cmd, cwd=repo, env=env, timeout=300)
        log.append("COMMAND\n" + cmdtext(cmd) + f"\nEXIT CODE\n{p.returncode}\nSTDOUT\n{p.stdout}\nSTDERR\n{p.stderr}\n")
        if check and p.returncode != 0:
            raise RuntimeError("command failed: " + cmdtext(cmd))
        return p
    try:
        rr([git, "init"]); rr([git, "config", "user.email", "preos-phase25@example.invalid"]); rr([git, "config", "user.name", "PREOS Phase25"])
        (repo / "README.md").write_text("baseline\n", encoding="utf-8")
        (repo / "project-contract.json").write_text(json.dumps({"project_id":"phase25-preflight"}, indent=2)+"\n", encoding="utf-8")
        (repo / "task-packet.md").write_text("# TP-001\n", encoding="utf-8")
        (repo / "tests").mkdir(); (repo / "tests" / "verify_value.py").write_text("print('PASS')\n", encoding="utf-8")
        rr([git, "add", "."]); rr([git, "commit", "-m", "baseline"])
        project="phase25-preflight"
        rr([sys.executable, str(preos / "scripts" / "init-project-state.py"), project, "--repo", str(repo)])
        rr([sys.executable, str(preos / "scripts" / "checkpoint-state.py"), project, "--repo", str(repo),
            "--kind", "soft", "--event", "SESSION_INTERRUPTED", "--project-contract", "project-contract.json",
            "--project-contract-version", "PC-1", "--task-packet", "task-packet.md", "--task-packet-id", "TP-001",
            "--last-verified-action", "bounded edit complete", "--next-unverified-action", "python tests/verify_value.py",
            "--pending-test", "python tests/verify_value.py", "--release-status", "NOT_AUTHORIZED"])
        recovered = rr([sys.executable, str(preos / "scripts" / "recover-state.py"), project, "--repo", str(repo)], check=False)
        data = json.loads(recovered.stdout)
        expected = "re-run uncertain test: python tests/verify_value.py"
        if recovered.returncode != 0 or data.get("status") != "SAFE_TO_RESUME" or data.get("next_unverified_action") != expected:
            raise RuntimeError("deterministic recovery preflight mismatch\n" + json.dumps(data, indent=2))
        log.append("PREFLIGHT_ASSERTION\nSAFE_TO_RESUME exact pending-test precedence PASS\n")
    except Exception as exc:
        (report_dir / "deterministic-recovery-preflight.log").write_text("\n\n".join(log) + "\n\nERROR\n" + str(exc), encoding="utf-8")
        raise AcceptanceFailure("PHASE_25_FAIL_RECOVERY", "PREOS_RECOVERY_PREFLIGHT", "DETERMINISTIC_RECOVERY_PREFLIGHT",
                                "Deterministic PREOS recovery preflight failed before Codex was started.\n" + str(exc))
    finally:
        shutil.rmtree(base, ignore_errors=True)
    (report_dir / "deterministic-recovery-preflight.log").write_text("\n\n".join(log), encoding="utf-8")


def gstack_setup(gstack: Path, home: Path, report_dir: Path, bash: Path, bun: str) -> list[str]:
    env = os.environ.copy()
    env["WIN_CODEX_HOME"] = str(home)
    env["WIN_BUN_DIR"] = str(Path(bun).resolve().parent)
    env["GSTACK_SETUP_RUNNING"] = "1"
    preflight_cmd = 'export CODEX_HOME="$(cygpath -u "$WIN_CODEX_HOME")"; export PATH="$(cygpath -u "$WIN_BUN_DIR"):$PATH"; command -v bun; bun --version; command -v cygpath'
    pre = run([bash, "-lc", preflight_cmd], cwd=gstack, env=env, timeout=120)
    if pre.returncode != 0:
        raise AcceptanceFailure("PHASE_24_FAIL_SKILL_DISCOVERY", "ENVIRONMENT", "GSTACK_BASH_PREFLIGHT",
                                "Bun or cygpath was not usable inside Git Bash.\n" + pre.stdout + "\n" + pre.stderr)
    setup_cmd = ('export CODEX_HOME="$(cygpath -u "$WIN_CODEX_HOME")"; '
                 'export PATH="$(cygpath -u "$WIN_BUN_DIR"):$PATH"; '
                 './setup --host codex --prefix --no-team --no-plan-tune-hooks --quiet')
    p = run([bash, "-lc", setup_cmd], cwd=gstack, env=env, timeout=1800)
    (report_dir / "gstack-setup.log").write_text(
        "PRECHECK\n" + pre.stdout + pre.stderr + "\n\nSETUP\n" + p.stdout + p.stderr + f"\nEXIT={p.returncode}\n",
        encoding="utf-8",
    )
    if p.returncode != 0:
        text = p.stdout + "\n" + p.stderr
        verdict = "PHASE_25_BLOCKED_EXTERNAL_SERVICE" if external_failure(text) else "PHASE_24_FAIL_SKILL_DISCOVERY"
        raise AcceptanceFailure(verdict, "GSTACK_SETUP", "INSTALL_GSTACK", "gstack supported Codex setup failed.\n" + excerpt(text))
    generated = gstack / ".agents" / "skills"
    names = sorted(p.name for p in generated.glob("gstack-*") if p.is_dir() and (p / "SKILL.md").is_file())
    if not names:
        raise AcceptanceFailure("PHASE_24_FAIL_SKILL_DISCOVERY", "GSTACK_SETUP", "INSTALL_GSTACK",
                                "gstack setup produced no generated gstack-* Codex skills.")
    return names


def verify_installed_skills(home: Path, sources: dict[str, Path], generated_gstack: list[str], unrelated_before: set[str]) -> dict:
    skills = home / "skills"
    problems = []
    hashes = {}
    blueprint_source = sources["wed_dev_skill"] / "SKILL.md"
    blueprint_installed = skills / "ai-product-delivery-blueprint" / "SKILL.md"
    if read_skill_name(blueprint_installed) != "ai-product-delivery-blueprint":
        problems.append("Blueprint installed SKILL.md name mismatch")
    elif sha256_file(blueprint_source) != sha256_file(blueprint_installed):
        problems.append("Blueprint installed SKILL.md hash mismatch")
    else:
        hashes["ai-product-delivery-blueprint"] = sha256_file(blueprint_installed)
    preos_src = sources["PREOS"]
    for name in PREOS_SKILLS:
        src = preos_src / "SKILL.md" if name == "preos" else preos_src / name / "SKILL.md"
        dst = skills / name / "SKILL.md"
        if read_skill_name(dst) != name:
            problems.append(f"{name} installed SKILL.md name mismatch")
        elif sha256_file(src) != sha256_file(dst):
            problems.append(f"{name} installed SKILL.md hash mismatch")
        else:
            hashes[name] = sha256_file(dst)
    generated_root = sources["gstack"] / ".agents" / "skills"
    for name in generated_gstack:
        src = generated_root / name / "SKILL.md"
        dst = skills / name / "SKILL.md"
        if not dst.is_file():
            problems.append(f"missing installed gstack skill: {name}")
        elif sha256_file(src) != sha256_file(dst):
            problems.append(f"gstack installed SKILL.md hash mismatch: {name}")
        else:
            hashes[name] = sha256_file(dst)
    for required in REQUIRED_SKILLS:
        if not (skills / required / "SKILL.md").is_file():
            problems.append(f"required skill missing: {required}")
    current_names = {p.name for p in skills.iterdir()} if skills.exists() else set()
    missing_unrelated = unrelated_before - current_names
    if missing_unrelated:
        problems.append("unrelated skills disappeared: " + ", ".join(sorted(missing_unrelated)))
    if problems:
        raise AcceptanceFailure("PHASE_24_FAIL_SKILL_DISCOVERY", "SKILL_VERIFICATION", "VERIFY_INSTALLED_SKILLS",
                                "\n".join(problems))
    return hashes


def candidate_only_main() -> int:
    if os.name != "nt":
        raise AcceptanceFailure("PHASE_24_FAIL_SKILL_DISCOVERY", "ENVIRONMENT", "ENVIRONMENT_PREFLIGHT",
                                "Windows is required for candidate-only CI validation.")
    if sys.version_info[:2] != (3, 13):
        raise AcceptanceFailure("PHASE_24_FAIL_SKILL_DISCOVERY", "ENVIRONMENT", "ENVIRONMENT_PREFLIGHT",
                                f"Python 3.13 required, found {sys.version.split()[0]}")
    git = shutil.which("git"); bun = shutil.which("bun")
    if not git or not bun:
        raise AcceptanceFailure("PHASE_24_FAIL_SKILL_DISCOVERY", "ENVIRONMENT", "ENVIRONMENT_PREFLIGHT",
                                f"git={git} bun={bun}")
    bash = find_git_bash(git)
    home = codex_home(); report_dir = home / "phase24-25-reports" / ("ci-r3-" + now_stamp())
    report_dir.mkdir(parents=True, exist_ok=True)
    verified_sources_root = home / "framework-sources" / "verified" / ("ci-r3-" + now_stamp())
    verified_sources_root.mkdir(parents=True, exist_ok=False)
    remote_log=[]
    for _name,(key,url,expected) in SOURCE_SPECS.items():
        remote_head(git,key,url,expected,remote_log)
    (report_dir/"remote-source-preflight.log").write_text("\n\n".join(remote_log),encoding="utf-8")
    checkout_log=[]; sources={}
    for name,(_key,url,expected) in SOURCE_SPECS.items():
        sources[name]=checkout_exact_source(git,name,url,expected,verified_sources_root,checkout_log)
    (report_dir/"source-checkout.log").write_text("\n\n".join(checkout_log),encoding="utf-8")
    run_preos_validation(sources["PREOS"],report_dir)
    deterministic_recovery_preflight(sources["PREOS"],report_dir,git)
    candidate_home=home/"phase24-candidates"/("ci-r3-"+now_stamp()); candidate_skills=candidate_home/"skills"; candidate_skills.mkdir(parents=True)
    copy_tree(sources["wed_dev_skill"],candidate_skills/"ai-product-delivery-blueprint")
    for name in PREOS_SKILLS:
        src=sources["PREOS"] if name=="preos" else sources["PREOS"]/name
        copy_tree(src,candidate_skills/name)
    generated_gstack=gstack_setup(sources["gstack"],candidate_home,report_dir,bash,bun)
    verify_installed_skills(candidate_home,sources,generated_gstack,set())
    print("CANDIDATE_ONLY_PASS")
    print(f"report={report_dir}")
    return 0


def self_test() -> int:
    problems=[]
    try:
        p=run([sys.executable,"-c","pass"],timeout=30)
        if not isinstance(p.stdout,str) or not isinstance(p.stderr,str):
            problems.append("run output normalization failed")
    except Exception as exc:
        problems.append("run normalization exception: "+repr(exc))
    if problems:
        print("SELF_TEST_FAIL"); print("\n".join(problems)); return 1
    print("SELF_TEST_PASS"); return 0


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--self-test",action="store_true")
    parser.add_argument("--candidate-only",action="store_true")
    args=parser.parse_args()
    if args.self_test:
        return self_test()
    if args.candidate_only:
        try:
            return candidate_only_main()
        except AcceptanceFailure as exc:
            print(exc.verdict)
            print(f"failure_class={exc.failure_class}")
            print(f"stage={exc.stage}")
            print(exc.detail)
            return 2
        except Exception:
            traceback.print_exc()
            return 3
    raise SystemExit("This CI harness only exposes --self-test and --candidate-only. The user-facing resolver is packaged separately after Windows CI passes.")


if __name__ == "__main__":
    raise SystemExit(main())
