#!/usr/bin/env python3
from __future__ import annotations
import argparse,os,shutil
from common import load_config,timezone_name,uber_config,assert_environment_safe
from resolve_ride_context import get_current_location
from uber_tokens import token_exists

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--config'); ap.add_argument('--environment'); ap.add_argument('--demo',action='store_true'); args=ap.parse_args()
    checks=[]
    try: cfg=load_config(args.config); checks.append(('configuration',True,''))
    except Exception as e: cfg={}; checks.append(('configuration',False,str(e)))
    try: timezone_name(cfg); checks.append(('timezone',True,''))
    except Exception as e: checks.append(('timezone',False,str(e)))
    u=cfg.get('uber') or {}; checks.append(('client_id configured',bool(os.getenv('HERMES_UBER_CLIENT_ID') or u.get('client_id')),'')); checks.append(('OAuth redirect configured',bool(os.getenv('HERMES_UBER_REDIRECT_URI') or u.get('redirect_uri')),'')); checks.append(('Keychain',bool(shutil.which('security')),'macOS security command required'))
    try: env=assert_environment_safe(cfg,args.environment); checks.append(('environment',True,env))
    except Exception as e: checks.append(('environment',False,str(e)))
    checks.append(('Uber OAuth',token_exists('owner'),'connect account first'))
    checks.append(('request scope','request' in (u.get('scopes') or []),'request scope missing'))
    checks.append(('profile scope','profile' in (u.get('scopes') or []),'profile needed for GET /v1.2/me'))
    checks.append(('iMessage',bool(((u.get('imessage_provider') or {}).get('argv'))),'shared provider not configured'))
    try: checks.append(('location',get_current_location(cfg) is not None,'configure current location provider/place'))
    except Exception as e: checks.append(('location',False,str(e)))
    checks.append(('calendar',bool(((u.get('calendar_provider') or {}).get('argv'))),'optional provider not configured'))
    print('Hermes Uber Healthcheck\n')
    for name,ok,detail in checks: print(f"[{'OK' if ok else 'FAIL'}] {name}"+(f': {detail}' if detail else ''))
    raise SystemExit(0 if all(ok for name,ok,d in checks if name not in {'calendar'}) else 1)
if __name__=='__main__':main()
