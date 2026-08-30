#!/usr/bin/env python3
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time


def cmdtext(cmd):
    return subprocess.list2cmdline([str(x) for x in cmd])


def parse_thread_id(text: str):
    for line in text.splitlines():
        try:
            obj=json.loads(line)
        except Exception:
            continue
        if obj.get("type")=="thread.started" and obj.get("thread_id"):
            return str(obj["thread_id"])
    return None


def codex_command(codex: Path, repo: Path):
    if os.name=="nt" and codex.suffix.lower() in {".cmd",".bat"}:
        inner=subprocess.list2cmdline([str(codex),"exec","--ephemeral","--json","--full-auto","-C",str(repo),"-"])
        return ["cmd.exe","/d","/s","/c",inner]
    return [str(codex),"exec","--ephemeral","--json","--full-auto","-C",str(repo),"-"]


def codex_exec_until_marker(codex: Path, repo: Path, prompt: str, env: dict[str,str], marker: Path):
    cmd=codex_command(codex,repo)
    stdout_lines=[]; stderr_lines=[]
    proc=subprocess.Popen(cmd,cwd=repo,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
    def reader(stream,sink):
        try:
            for line in iter(stream.readline,""):
                sink.append(line)
        finally:
            try: stream.close()
            except Exception: pass
    t1=threading.Thread(target=reader,args=(proc.stdout,stdout_lines),daemon=True)
    t2=threading.Thread(target=reader,args=(proc.stderr,stderr_lines),daemon=True)
    t1.start(); t2.start()
    assert proc.stdin is not None
    proc.stdin.write(prompt); proc.stdin.close()
    deadline=time.time()+60
    marker_seen=False; forced=False; timed_out=False
    while time.time()<deadline:
        if marker.is_file():
            marker_seen=True; break
        if proc.poll() is not None: break
        time.sleep(0.1)
    if marker_seen:
        time.sleep(0.2)
        if proc.poll() is None:
            subprocess.run(["taskkill.exe","/PID",str(proc.pid),"/T","/F"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            forced=True
    elif proc.poll() is None:
        timed_out=True
        subprocess.run(["taskkill.exe","/PID",str(proc.pid),"/T","/F"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try: proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill(); proc.wait(timeout=5)
    t1.join(timeout=5); t2.join(timeout=5)
    return subprocess.CompletedProcess(cmd,proc.returncode if proc.returncode is not None else -999,"".join(stdout_lines),"".join(stderr_lines)),marker_seen,forced,timed_out


def codex_exec(codex: Path, repo: Path, prompt: str, env: dict[str,str]):
    p=subprocess.run(codex_command(codex,repo),cwd=repo,env=env,input=prompt,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60)
    return subprocess.CompletedProcess(p.args,p.returncode,p.stdout or "",p.stderr or "")


def main():
    assert os.name=="nt", "Windows required"
    with tempfile.TemporaryDirectory(prefix="phase25-process-ci-") as td:
        base=Path(td); repo=base/"repo with spaces"; bindir=base/"fake codex dir"
        repo.mkdir(); bindir.mkdir()
        fake_py=bindir/"fake_codex.py"
        fake_cmd=bindir/"codex.cmd"
        fake_py.write_text(
            "import json, os, sys, time\n"
            "from pathlib import Path\n"
            "prompt=sys.stdin.read()\n"
            "thread=os.environ.get('FAKE_THREAD_ID','thread-default')\n"
            "print(json.dumps({'type':'thread.started','thread_id':thread}), flush=True)\n"
            "print(json.dumps({'type':'turn.started'}), flush=True)\n"
            "marker=os.environ.get('FAKE_MARKER_PATH')\n"
            "if marker:\n"
            "    Path(marker).write_text('durable\\n', encoding='utf-8')\n"
            "    print('FAKE_MARKER_WRITTEN', flush=True)\n"
            "    while True: time.sleep(1)\n"
            "print(json.dumps({'type':'turn.completed'}), flush=True)\n",
            encoding="utf-8",
        )
        fake_cmd.write_text('@echo off\r\npython "%~dp0fake_codex.py" %*\r\n',encoding="utf-8")

        marker=repo/"durable-marker.json"
        env1=os.environ.copy(); env1["FAKE_THREAD_ID"]="thread-one"; env1["FAKE_MARKER_PATH"]=str(marker)
        first,marker_seen,forced,timed_out=codex_exec_until_marker(fake_cmd,repo,"first prompt over stdin",env1,marker)
        assert marker_seen, first.stderr
        assert forced, "first fake Codex process tree was not force-terminated"
        assert not timed_out
        assert parse_thread_id(first.stdout)=="thread-one", first.stdout

        env2=os.environ.copy(); env2["FAKE_THREAD_ID"]="thread-two"; env2.pop("FAKE_MARKER_PATH",None)
        second=codex_exec(fake_cmd,repo,"fresh prompt over stdin",env2)
        assert second.returncode==0, second.stderr
        assert parse_thread_id(second.stdout)=="thread-two", second.stdout
        assert parse_thread_id(second.stdout)!=parse_thread_id(first.stdout)
        assert "first prompt" not in second.stdout
        print("WINDOWS_PHASE25_PROCESS_CONTROL_PASS")
        print("first_command="+cmdtext(codex_command(fake_cmd,repo)))

if __name__=="__main__":
    main()
