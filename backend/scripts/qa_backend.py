"""Reproduce Linux tests; --sqlserver redirects all test writes into generated scratch databases."""
import argparse
from scripts.macro4_support import ROOT,docker

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--real',action='store_true');parser.add_argument('--sqlserver',action='store_true');args=parser.parse_args()
    if not args.real:parser.error('--real required for local Docker')
    command=['run','--rm','-T','--no-deps','-e','APP_ENV=development','-v',f'{ROOT / "backend/tests"}:/app/tests:ro','sql-init','python']
    if args.sqlserver:
        # Even tests that normally use the configured engine see this scratch DB.
        script="""import os,subprocess
from tests.sqlserver_support import isolated_sqlserver
with isolated_sqlserver() as scratch:
    result=subprocess.run(['python','-m','pytest','-q','--sqlserver','-p','no:cacheprovider'],env=dict(os.environ,DB_NAME=scratch.url.database,APP_ENV='development'))
    code=result.returncode
raise SystemExit(code)
"""
        output=docker(*command,'-',input=script.encode(),timeout=600)
    else:output=docker(*command,'-m','pytest','-q','-p','no:cacheprovider',timeout=600)
    print(output)

if __name__=='__main__':main()
