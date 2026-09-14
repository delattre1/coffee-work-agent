#!/usr/bin/env python3
from __future__ import annotations
import argparse
from common import load_config,assert_environment_safe,json_out
from uber_oauth import config_values,refresh_access_token
from uber_tokens import get_valid_access_token
from uber_api import UberClient

def client(cfg,env,user_id):
    cid,secret,_,_=config_values(cfg)
    tok=get_valid_access_token(user_id,lambda rt: refresh_access_token(cid,secret,rt))
    return UberClient(tok,env)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--config'); ap.add_argument('--environment'); ap.add_argument('--user-id',default='owner'); sub=ap.add_subparsers(dest='cmd',required=True)
    s=sub.add_parser('status'); s.add_argument('request_id')
    c=sub.add_parser('cancel'); c.add_argument('request_id'); c.add_argument('--approved',action='store_true')
    x=sub.add_parser('sandbox-status'); x.add_argument('request_id'); x.add_argument('status')
    a=ap.parse_args(); cfg=load_config(a.config); env=assert_environment_safe(cfg,a.environment); cli=client(cfg,env,a.user_id)
    if a.cmd=='status': json_out(cli.get_request(a.request_id))
    elif a.cmd=='cancel':
        if not a.approved: raise SystemExit('cancel requires explicit --approved confirmation')
        json_out({'canceled':True,'response':cli.cancel_request(a.request_id)})
    else:
        if env!='sandbox': raise SystemExit('sandbox-status is sandbox only')
        if not ((cfg.get('uber') or {}).get('sandbox_simulation_enabled')): raise SystemExit('sandbox simulation disabled in config')
        json_out({'updated':True,'response':cli.sandbox_set_status(a.request_id,a.status)})
if __name__=='__main__': main()
