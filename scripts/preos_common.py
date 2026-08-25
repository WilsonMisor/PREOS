from pathlib import Path
import json, hashlib, os, zipfile, gzip

GATE_STATES = ["GREEN","AMBER","RED","HUMAN REVIEW","UNKNOWN"]
PROTECTED_AUTHORITY_WORDS = {"AI","CODEX","GSTACK","LLM","AGENT","PREOS"}

def preos_root(start=None):
    p=Path(start or Path.cwd()).resolve()
    for c in [p,*p.parents]:
        if (c/'SKILL.md').is_file() and (c/'references').is_dir() and (c/'source-package').is_dir():
            return c
    return Path(__file__).resolve().parents[1]

def load_json(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def load_source_json(name, root=None):
    with zipfile.ZipFile(preos_root(root)/'source-package'/'original-package.zip') as zf:
        return json.loads(zf.read(name).decode('utf-8'))
def dump_json(path,obj):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+"\n",encoding='utf-8')
def sha256_file(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()
def iter_risks(root=None):
    p=preos_root(root)/'references'/'risks'/'atomic-risk-catalogue.jsonl.gz'
    with gzip.open(p,'rt',encoding='utf-8') as fh:
        for line in fh:
            line=line.strip()
            if line: yield json.loads(line)
def runtime_root():
    env=os.environ.get('PREOS_STATE_ROOT')
    if env: return Path(env).expanduser()
    if os.name=='nt': return Path(os.environ.get('LOCALAPPDATA',Path.home()))/'PREOS'
    return Path(os.environ.get('XDG_STATE_HOME',Path.home()/'.local/state'))/'preos'
