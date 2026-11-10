"""Read Windows demo, send snapshot via stdin to isolated SQL; never modify source."""
import json
import os
from pathlib import Path
import shutil
import subprocess
from sqlalchemy import text,event
import config
from database.connection import engine
from scripts.ae4_preservation import snapshot,check_constraints

def main():
    if config.DB_NAME!='TurismoPosadas' or config.DB_USER:
        raise RuntimeError('Run with the existing Windows demo configuration')
    def read_only(conn,cursor,statement,params,context,many):
        if not statement.lstrip().upper().startswith(('SELECT','DBCC')):
            raise RuntimeError('Source writes forbidden')
    event.listen(engine,'before_cursor_execute',read_only)
    try:
        before=snapshot(engine);check_constraints(engine)
        tables={}
        with engine.connect() as db:
            for name in before:
                order='event_id' if name=='eventos_procesados' else 'id'
                tables[name]=[dict(row) for row in db.execute(text(f'SELECT * FROM dbo.[{name}] ORDER BY [{order}]')).mappings()]
        docker=shutil.which('docker') or str(Path(os.environ['LOCALAPPDATA'])/'Programs/DockerDesktop/resources/bin/docker.exe')
        environment=dict(os.environ);environment['PATH']=str(Path(docker).parent)+os.pathsep+environment.get('PATH','')
        command=[docker,'--context','desktop-linux','compose','run','--rm','-T','--no-deps','sql-init','python','-m','scripts.import_container_demo']
        result=subprocess.run(command,cwd=config.BASE_DIR.parent,env=environment,
            input=json.dumps({'snapshot':before,'tables':tables},default=str).encode(),capture_output=True,timeout=120)
        if result.returncode:
            # SQL parameters are hidden; stdout only contains counts/hashes, never rows.
            raise RuntimeError('Isolated import failed: '+result.stderr.decode(errors='replace')[-2500:])
        after=snapshot(engine)
        if after!=before:raise RuntimeError('Source changed during snapshot copy')
        check_constraints(engine)
        report={'source_preserved':True,'source_snapshot':after,'target':json.loads(result.stdout),'dbcc_violations':0}
        path=config.BASE_DIR.parent/'docs/AE4_VALIDATION.json'
        evidence=json.loads(path.read_text(encoding='utf-8'));evidence.setdefault('macro3',{})['isolated_demo_copy']=report
        path.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        print('Demo copied to isolated Compose SQL; source hashes intact; DBCC clean. No credentials displayed.')
    finally:event.remove(engine,'before_cursor_execute',read_only)

if __name__=='__main__':main()
