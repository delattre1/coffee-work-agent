#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,time
from common import load_config,assert_environment_safe,json_out,SafetyError
from uber_oauth import config_values,refresh_access_token
from uber_tokens import get_valid_access_token
from uber_api import UberClient

def _point_from_payload(payload,prefix):
    return {'latitude':float(payload[f'{prefix}_latitude']),'longitude':float(payload[f'{prefix}_longitude'])}
def _same_point(a,b,tol=1e-6):
    try:return abs(float(a['latitude'])-float(b['latitude']))<=tol and abs(float(a['longitude'])-float(b['longitude']))<=tol
    except Exception:return False

def approval_matches(approval,payload,estimate):
    if approval.get('approved') is not True:return False
    fare=((estimate or {}).get('fare') or {})
    if approval.get('fare_id')!=fare.get('fare_id') or approval.get('product_id')!=payload.get('product_id'): return False
    if not _same_point(approval.get('pickup') or {},_point_from_payload(payload,'start')): return False
    if not _same_point(approval.get('destination') or {},_point_from_payload(payload,'end')): return False
    return True

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--config'); ap.add_argument('--environment'); ap.add_argument('--user-id',default='owner'); ap.add_argument('--payload',required=True); ap.add_argument('--estimate',required=True); ap.add_argument('--approval',required=True); args=ap.parse_args()
    cfg=load_config(args.config); env=assert_environment_safe(cfg,args.environment); payload=json.loads(args.payload); est=json.loads(args.estimate); approval=json.loads(args.approval)
    if not approval_matches(approval,payload,est): raise SafetyError('approval does not match current pickup/destination/product/fare')
    fare=(est.get('fare') or {}); expires=fare.get('expires_at')
    if expires and time.time() >= float(expires): raise SafetyError('fare expired; estimate again and re-approve')
    payload['fare_id']=fare.get('fare_id')
    if not payload['fare_id']: raise SafetyError('fare_id missing')
    cid,secret,_,_=config_values(cfg); tok=get_valid_access_token(args.user_id,lambda rt: refresh_access_token(cid,secret,rt)); json_out(UberClient(tok,env).request_ride(payload))
if __name__=='__main__':main()
