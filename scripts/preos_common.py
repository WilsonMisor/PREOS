from pathlib import Path
import json, hashlib, os, zipfile, base64, io

GATE_STATES = ["GREEN","AMBER","RED","HUMAN REVIEW","UNKNOWN"]
PROTECTED_AUTHORITY_WORDS = {"AI","CODEX","GSTACK","LLM","AGENT","PREOS"}

def preos_root(start=None):
    p=Path(start or Path.cwd()).resolve()
    for c in [p,*p.parents]:
        if (c/'SKILL.md').is_file() and (c/'references').is_dir() and (c/'source-package').is_dir():
            return c
    return Path(__file__).resolve().parents[1]

def load_json(path): return json.loads(Path(path).read_text(encoding='utf-8'))
def source_package_bytes(root=None):
    root=preos_root(root)
    manifest=load_json(root/'source-package/PACKAGE-CHUNKS.json')
    parts=[]
    for item in manifest['chunks']:
        p=root/'source-package/package-chunks'/item['name']
        data=p.read_bytes()
        if len(data)!=item['bytes'] or hashlib.sha256(data).hexdigest()!=item['sha256']:
            raise ValueError(f"source package chunk integrity failure: {item['name']}")
        parts.append(data)
    raw=base64.b64decode(b''.join(parts),validate=True)
    if len(raw)!=manifest['reconstructed_bytes'] or hashlib.sha256(raw).hexdigest()!=manifest['reconstructed_sha256']:
        raise ValueError('reconstructed source package integrity failure')
    return raw

def open_source_zip(root=None):
    return zipfile.ZipFile(io.BytesIO(source_package_bytes(root)))

def load_source_json(name, root=None):
    with open_source_zip(root) as zf:
        return json.loads(zf.read(name).decode('utf-8'))

def dump_json(path,obj):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+"\n",encoding='utf-8')
def sha256_file(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()
def iter_risks(root=None):
    with open_source_zip(root) as zf:
        with zf.open('atomic_risk_catalogue.jsonl') as raw:
            text=io.TextIOWrapper(raw,encoding='utf-8')
            for line in text:
                line=line.strip()
                if line: yield json.loads(line)
def runtime_root():
    env=os.environ.get('PREOS_STATE_ROOT')
    if env: return Path(env).expanduser()
    if os.name=='nt': return Path(os.environ.get('LOCALAPPDATA',Path.home()))/'PREOS'
    return Path(os.environ.get('XDG_STATE_HOME',Path.home()/'.local/state'))/'preos'
