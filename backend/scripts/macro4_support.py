"""Local-only QA operator helpers. No shell interpolation of secrets."""
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[2]
STATE=ROOT/'backend/.demo/macro4-run.json'

def docker(*args, input=None, timeout=120):
    exe=shutil.which('docker') or str(Path(os.environ['LOCALAPPDATA'])/'Programs/DockerDesktop/resources/bin/docker.exe')
    env=dict(os.environ);env['PATH']=str(Path(exe).parent)+os.pathsep+env.get('PATH','')
    p=subprocess.run([exe,'--context','desktop-linux','compose',*args],cwd=ROOT,env=env,
                     input=input,capture_output=True,timeout=timeout)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[-2000:])
    return p.stdout.decode(errors='replace')

def helper(data):
    source=ROOT/'backend/scripts/macro4_fixture.py'
    output=docker('run','--rm','-T','--no-deps','-v',f'{source}:/app/scripts/macro4_fixture.py:ro',
                  'sql-init','python','-m','scripts.macro4_fixture',input=json.dumps(data).encode())
    return json.loads(output)

def state():
    return json.loads(STATE.read_text(encoding='utf-8'))

def evidence(name,data):
    p=ROOT/'docs/evidence'/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
