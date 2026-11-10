"""Progress heartbeat for container probes; no business data in its file."""
import json
import os
from pathlib import Path
import re
import tempfile
import time
import config

def heartbeat_path():
    name=re.sub(r"[^a-zA-Z0-9_-]","_",config.SERVICE_NAME)
    return Path(tempfile.gettempdir())/f"pt-{name}.heartbeat"

def heartbeat(ready):
    path=heartbeat_path(); temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'pid':os.getpid(),'timestamp':time.time(),'ready':bool(ready)}),encoding='utf-8')
    temporary.replace(path)

def schedule(connection):
    def tick():
        if connection.is_open:
            heartbeat(True)
            connection.call_later(5,tick)
    tick()
