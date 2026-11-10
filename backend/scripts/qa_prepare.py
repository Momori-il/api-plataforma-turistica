"""Prepare exactly one tagged, removable QA fixture; never reveal credentials."""
import argparse
import json
import secrets
from uuid import uuid4
from scripts.macro4_support import STATE,helper

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--real',action='store_true');args=parser.parse_args()
    if not args.real:parser.error('--real required')
    if STATE.exists():raise RuntimeError('Existing QA state: finish/clean it before preparing another fixture')
    tag='macro4-'+uuid4().hex;password=secrets.token_urlsafe(24)
    fixture=helper({'action':'setup','tag':tag,'password':password})
    STATE.write_text(json.dumps({'fixture':fixture,'password':password}),encoding='utf-8')
    print('Tagged Docker QA fixture ready. Credentials remain only in ignored backend/.demo/macro4-run.json.')

if __name__=='__main__':main()
