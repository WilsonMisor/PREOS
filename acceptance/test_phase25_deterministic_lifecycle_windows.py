#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

PREOS = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(cmd, *, cwd: Path, env: dict[str,str], check=False):
    p=subprocess.run([str(x) for x in cmd],cwd=cwd,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    p=subprocess.CompletedProcess(p.args,p.returncode,p.stdout or "",p.stderr or "")
    if check and p.returncode!=0:
        raise AssertionError(f"command failed: {subprocess.list2cmdline([str(x) for x in cmd])}\nrc={p.returncode}\nstdout={p.stdout}\nstderr={p.stderr}")
    return p


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    assert os.name=="nt", "Windows required"
    assert sys.version_info[:2]==(3,13), sys.version
    with tempfile.TemporaryDirectory(prefix="phase25-lifecycle-ci-") as td:
        base=Path(td); repo=base/"disposable app with spaces"; state_root=base/"preos state with spaces"
        repo.mkdir()
        project="phase25-windows-ci"
        env=os.environ.copy(); env["PREOS_STATE_ROOT"]=str(state_root); env["PYTHONPATH"]=str(PREOS/"scripts")

        def rr(cmd,check=True): return run(cmd,cwd=repo,env=env,check=check)
        rr(["git","init"]); rr(["git","config","user.email","phase25-ci@example.invalid"]); rr(["git","config","user.name","Phase25 Windows CI"])
        (repo/".gitignore").write_text(
            ".preos_runtime_state/\nphase24_live_discovery.json\nphase25-drill-marker.json\nphase25_stage2_result.json\n"
            "evidence/\nverification-manifest.json\n.phase25_test_execution_marker\n__pycache__/\n",
            encoding="utf-8",
        )
        (repo/"requirements.md").write_text(
            "# Disposable requirement\n\nTP-001 changes value.json from v1 to v2. The deterministic test is the first unverified action after session loss.\n",
            encoding="utf-8",
        )
        (repo/"value.json").write_text('{"value":"v1"}\n',encoding="utf-8")
        (repo/"tests").mkdir()
        (repo/"tests"/"verify_value.py").write_text(
            "import json\nfrom pathlib import Path\n"
            "root=Path(__file__).resolve().parents[1]\n"
            "(root/'.phase25_test_execution_marker').write_text('executed\\n',encoding='utf-8')\n"
            "value=json.loads((root/'value.json').read_text(encoding='utf-8'))['value']\n"
            "if value != 'v2': raise SystemExit(f'FAIL expected v2, got {value!r}')\n"
            "print('PASS value is v2')\n",
            encoding="utf-8",
        )
        (repo/"project-contract.json").write_text(json.dumps({
            "schema_version":"1.0","project_id":project,"classification":"disposable local acceptance fixture",
            "bounded_implementation_engine":"OpenAI Codex","production_authorization":"NOT_AUTHORIZED",
            "source_hashes":[{"artifact":"requirements.md","sha256":sha256_file(repo/"requirements.md")}],
            "authority_boundary":{"preos":"runtime and recovery authority","gstack":"supplementary specialist context","codex":"bounded implementer","production_approval":"human only"},
        },indent=2)+"\n",encoding="utf-8")
        (repo/"task-packet.md").write_text(
            "# AI Task Packet TP-001\n\n## Scope\nChange only value.json from v1 to v2. Do not deploy. Do not push. Production remains NOT_AUTHORIZED.\n\n"
            "## Required checks\npython tests/verify_value.py\n\n## Required evidence\nEV-TP001-TEST\n",
            encoding="utf-8",
        )
        expected_test="python tests/verify_value.py"; expected_action="re-run uncertain test: python tests/verify_value.py"
        (repo/"phase25_fixture.json").write_text(json.dumps({"project_id":project,"expected_pending_test":expected_test,"expected_recovery_action":expected_action},indent=2)+"\n",encoding="utf-8")
        rr(["git","add","."]); rr(["git","commit","-m","phase25 disposable baseline"])

        initial=rr([sys.executable,"tests/verify_value.py"],check=False)
        assert initial.returncode!=0, "fixture test unexpectedly passed before bounded edit"
        (repo/".phase25_test_execution_marker").unlink(missing_ok=True)
        rr([sys.executable,PREOS/"scripts"/"init-project-state.py",project,"--repo",repo])

        # Bounded edit, but final verification remains deliberately pending.
        (repo/"value.json").write_text('{"value":"v2"}\n',encoding="utf-8")
        assert not (repo/".phase25_test_execution_marker").exists()
        soft=rr([sys.executable,PREOS/"scripts"/"checkpoint-state.py",project,"--repo",repo,
                 "--kind","soft","--event","SESSION_INTERRUPTED",
                 "--project-contract","project-contract.json","--project-contract-version","PC-1",
                 "--task-packet","task-packet.md","--task-packet-id","TP-001",
                 "--last-verified-action","bounded Codex edit complete",
                 "--next-unverified-action",expected_test,"--pending-test",expected_test,
                 "--pending-evidence","EV-TP001-TEST","--release-status","NOT_AUTHORIZED"])
        prod=state_root/"projects"/project/"production"
        current=load_json(prod/"CURRENT-STATE.json"); pipeline=load_json(prod/"PIPELINE-STATE.json")
        assert current["pending_test"]==expected_test and pipeline["pending_test"]==expected_test
        assert current["release_status"]=="NOT_AUTHORIZED" and pipeline["release_status"]=="NOT_AUTHORIZED"

        # Fresh-process deterministic recovery. Conversation memory is irrelevant.
        recovered=rr([sys.executable,PREOS/"scripts"/"recover-state.py",project,"--repo",repo],check=False)
        clean=json.loads(recovered.stdout)
        assert recovered.returncode==0, recovered.stderr
        assert clean.get("status")=="SAFE_TO_RESUME", clean
        assert clean.get("next_unverified_action")==expected_action, clean
        assert not (repo/".phase25_test_execution_marker").exists(), "test executed before deterministic recovery"

        # The pending deterministic test is the first unverified action actually executed.
        test_cmd=[sys.executable,"tests/verify_value.py"]
        test=rr(test_cmd,check=False)
        assert test.returncode==0, test.stdout+test.stderr
        assert (repo/".phase25_test_execution_marker").is_file()
        (repo/"evidence").mkdir(exist_ok=True)
        artifact=repo/"evidence"/"test_output.txt"
        artifact.write_text(
            "COMMAND\n"+subprocess.list2cmdline(test_cmd)+f"\nEXIT CODE\n{test.returncode}\nSTDOUT\n{test.stdout}\nSTDERR\n{test.stderr}\n",
            encoding="utf-8",
        )

        rollback_sha=rr(["git","rev-parse","HEAD"]).stdout.strip()
        rr(["git","add","value.json"]); rr(["git","commit","-m","phase25 bounded v2 change"])
        verified_sha=rr(["git","rev-parse","HEAD"]).stdout.strip()
        assert rr(["git","status","--porcelain"]).stdout.strip()=="", "ignored acceptance artifacts unexpectedly dirtied repo"

        capture=rr([sys.executable,PREOS/"scripts"/"capture-evidence.py",project,"EV-TP001-TEST","--repo",repo,
                    "--producer","OpenAI Codex Phase 25 disposable drill","--environment","disposable-local",
                    "--artifact","evidence/test_output.txt","--project-contract","project-contract.json",
                    "--task-packet","task-packet.md","--source","requirements.md","--test-definition","tests/verify_value.py",
                    "--test-or-command","python tests/verify_value.py","--result","PASS"])
        manifest={
            "schema_version":"1.0",
            "checks":[{"id":"TP-001-deterministic-test","status":"PASS","command_or_test":"python tests/verify_value.py","evidence_id":"EV-TP001-TEST"}],
            "evidence_ids":["EV-TP001-TEST"],"traceability":"UPDATED","rollback_point":rollback_sha,
            "notes":"Disposable acceptance only. Production authorization remains separate.",
        }
        (repo/"verification-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
        assert rr(["git","status","--porcelain"]).stdout.strip()==""
        hard=rr([sys.executable,PREOS/"scripts"/"checkpoint-state.py",project,"--repo",repo,
                 "--kind","hard","--event","IMPLEMENTATION_COMPLETE",
                 "--project-contract","project-contract.json","--project-contract-version","PC-1",
                 "--task-packet","task-packet.md","--task-packet-id","TP-001",
                 "--last-verified-action","python tests/verify_value.py PASS",
                 "--next-unverified-action","human production authorization remains separate",
                 "--verification-manifest",repo/"verification-manifest.json","--release-status","NOT_AUTHORIZED"])
        current=load_json(prod/"CURRENT-STATE.json")
        assert current.get("checkpoint_kind")=="HARD"
        assert current.get("release_status")=="NOT_AUTHORIZED"

        # gstack continuity docs must exist in the isolated candidate home and remain supplementary.
        ch=Path(os.environ["CODEX_HOME"])
        for skill in ("gstack-context-restore","gstack-preos-handoff"):
            path=ch/"skills"/skill/"SKILL.md"
            assert path.is_file(), f"missing candidate {skill}"
            text=path.read_text(encoding="utf-8",errors="replace")
            assert "PREOS" in text or "recovery" in text.lower(), f"{skill} does not preserve PREOS/recovery semantics"

        # Harmless post-checkpoint disagreement must fail closed.
        original=(repo/"value.json").read_text(encoding="utf-8")
        (repo/"value.json").write_text('{"value":"v3"}\n',encoding="utf-8")
        negative=rr([sys.executable,PREOS/"scripts"/"recover-state.py",project,"--repo",repo],check=False)
        neg=json.loads(negative.stdout)
        assert neg.get("status")=="RECOVERY_CONFLICT", neg
        (repo/"value.json").write_text(original,encoding="utf-8")
        assert rr(["git","status","--porcelain"]).stdout.strip()==""

        print("WINDOWS_PHASE25_DETERMINISTIC_LIFECYCLE_PASS")
        print(f"verified_commit={verified_sha}")
        print(f"release_status={current.get('release_status')}")
        print(f"negative_status={neg.get('status')}")

if __name__=="__main__":
    main()
