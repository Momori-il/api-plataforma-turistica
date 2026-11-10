"""Remove only tagged QA rows after confirmed delivery; restore workers even on failure."""
import argparse
import time
from scripts.macro4_support import STATE,state,helper,docker,evidence

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--real',action='store_true');args=parser.parse_args()
    if not args.real:parser.error('--real required')
    s=state();f=s['fixture'];data={'tag':f['tag'],'fixture':f}
    end=time.monotonic()+60
    while True:
        result=helper({'action':'inspect',**data})
        if result['pending_events']==0 and result['pending_effects']==0:break
        if time.monotonic()>=end:raise RuntimeError('Pending delivery/effects: fixture retained for inspection')
        time.sleep(1)
    # Let ACKs following Inbox commits settle before stopping. Do not purge queues.
    time.sleep(2)
    workers=['outbox-relay','audit-worker','notifications-worker','availability-worker']
    try:
        docker('stop',*workers)
        queue_check="from messaging.rabbitmq import get_connection; from messaging.worker import queue_name; c=get_connection(); ch=c.channel(); assert all(ch.queue_declare(queue=queue_name(n),passive=True).method.message_count==0 for n in ['audit','notifications','availability']), 'Messages remain; resume workers before cleanup'; c.close()"
        docker('exec','-T','core-api','python','-c',queue_check)
        result=helper({'action':'cleanup',**data})
        redis_cleanup=f"from services.redis_support import client,prefix; import config; r=client(); base=prefix(config.DB_NAME); keys=[k for namespace in ['h:{int(f['hotel'])}','a:{int(f['activity'])}'] for k in r.scan_iter(base+':avail:v1:'+namespace+':*')]; r.delete(*keys) if keys else None"
        docker('exec','-T','core-api','python','-c',redis_cleanup)
        evidence('system/cleanup.json',result)
        STATE.unlink()
        print('QA rows removed; original copied dataset hashes restored; DBCC clean.')
    finally:docker('start',*workers)

if __name__=='__main__':main()
