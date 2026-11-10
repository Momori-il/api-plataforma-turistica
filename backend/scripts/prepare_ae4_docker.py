"""Generate local-only integration secrets without displaying their values."""
import os
from pathlib import Path
import secrets
from urllib.parse import quote
from config import BASE_DIR

def prepare():
    folder=BASE_DIR/'.demo/ae4-docker'
    folder.mkdir(parents=True,exist_ok=True)
    if os.name!='nt':folder.chmod(0o700)
    def value(name):
        path=folder/name
        if not path.exists():
            with path.open('x',encoding='utf-8') as handle:handle.write(('Aa1!' if name.startswith('sql_') else '')+secrets.token_urlsafe(36))
            try:path.chmod(0o600)
            except OSError:pass
        return path.read_text(encoding='utf-8').strip()
    for name in ['jwt_secret','metrics_token','sql_admin_password','sql_core_password','sql_read_password','sql_relay_password','sql_audit_password','sql_notifications_password']:
        value(name)
    redis_password=value('redis_password');rabbit_password=value('rabbitmq_password')
    for name,url in {'redis_url':f'redis://:{quote(redis_password,safe="")}@redis:6379/0',
                     'rabbitmq_url':f'amqp://ae4:{quote(rabbit_password,safe="")}@rabbitmq:5672/ae4'}.items():
        path=folder/name
        if not path.exists():path.write_text(url,encoding='utf-8')
    # Local Compose uses bind-mounted secrets. Private parent on the host;
    # mounted files must also be readable by non-root SQL/Redis/app UIDs.
    if os.name!='nt':
        for path in folder.iterdir():
            if path.is_file():path.chmod(0o444)
    print('Local integration secrets ready in backend/.demo/ae4-docker; values withheld.')
    return folder

if __name__=='__main__':prepare()
