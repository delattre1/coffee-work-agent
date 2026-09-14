#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,os,time
from common import load_config,assert_environment_safe,SafetyError,json_out,uber_config
from ride_state import epoch_ms
from uber_oauth import config_values,client_credentials_token
from uber_tokens import load_tokens,save_tokens,TokenStoreError,token_expired
from uber_api import UberClient

GUEST_TOKEN_ACCOUNT='guest-rides-app'

def guest_access_token(cfg):
    cid,secret,_,_=config_values(cfg)
    try:
        t=load_tokens(GUEST_TOKEN_ACCOUNT)
        if not token_expired(t): return t['access_token']
    except TokenStoreError: pass
    t=client_credentials_token(cid,secret,'guests.trips')
    save_tokens(GUEST_TOKEN_ACCOUNT,t)
    return t['access_token']

def headers_config(cfg,env):
    u=uber_config(cfg)
    org=os.getenv('HERMES_UBER_ORGANIZATION_UUID') or u.get('organization_uuid') or None
    run=os.getenv('HERMES_UBER_SANDBOX_RUN_UUID') or None
    if env=='sandbox' and not run:
        raise SafetyError('Guest Rides sandbox requires HERMES_UBER_SANDBOX_RUN_UUID from a sandbox run')
    return org,run

def select_guest_estimate(response,preferred):
    rows=(response or {}).get('product_estimates') or []
    usable=[]
    for r in rows:
        p=r.get('product') or {}; ei=r.get('estimate_info') or {}
        blocker=((r.get('fulfillment_indicators') or {}).get('request_blocker') or {}).get('block_type')
        if blocker=='BLOCK': continue
        if not p.get('scheduling_enabled') and not ((p.get('reserve_info') or {}).get('enabled')): continue
        if not ei.get('fare_id'): continue
        usable.append(r)
    if not usable: return None
    for r in usable:
        p=r.get('product') or {}
        if preferred and preferred.lower() in {str(p.get('display_name','')).lower(),str(p.get('short_description','')).lower(),str(p.get('product_group','')).lower()}:
            return r
    return usable[0]

def make_payload(guest,pickup,dropoff,product_id,fare_id,pickup_iso):
    if not guest or not guest.get('phone_number') or not guest.get('first_name') or not guest.get('last_name'):
        raise SafetyError('Guest Trips requires guest first_name, last_name and phone_number')
    g={k:v for k,v in guest.items() if v}
    return {'guest':g,'pickup':pickup,'dropoff':dropoff,'product_id':product_id,'fare_id':fare_id,'scheduling':{'pickup_time':epoch_ms(pickup_iso)}}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--config'); ap.add_argument('--environment'); sub=ap.add_subparsers(dest='cmd',required=True)
    e=sub.add_parser('estimate'); e.add_argument('--pickup',required=True); e.add_argument('--dropoff',required=True); e.add_argument('--pickup-time',required=True)
    c=sub.add_parser('create'); c.add_argument('--pickup',required=True); c.add_argument('--dropoff',required=True); c.add_argument('--pickup-time',required=True); c.add_argument('--estimate',required=True); c.add_argument('--approved',action='store_true')
    a=ap.parse_args(); cfg=load_config(a.config); env=assert_environment_safe(cfg,a.environment); u=uber_config(cfg)
    if not u.get('scheduled_enabled',False): raise SafetyError('scheduled rides disabled until Guest Rides access is configured')
    org,run=headers_config(cfg,env); cli=UberClient(guest_access_token(cfg),env); pickup=json.loads(a.pickup); dropoff=json.loads(a.dropoff); pickup_ms=epoch_ms(a.pickup_time)
    if a.cmd=='estimate':
        raw=cli.guest_estimates(pickup,dropoff,pickup_ms,org,run); chosen=select_guest_estimate(raw,u.get('default_product'))
        if not chosen: raise SafetyError('no schedulable Guest Ride product/fare returned')
        json_out({'selected':chosen,'raw':raw}); return
    if not a.approved: raise SafetyError('scheduled paid ride requires explicit approval')
    est=json.loads(a.estimate); selected=est.get('selected') or est; product=selected.get('product') or {}; info=selected.get('estimate_info') or {}; fare_id=info.get('fare_id')
    if not product.get('product_id') or not fare_id: raise SafetyError('approved Guest Ride estimate missing product_id/fare_id')
    # Uber documents expires_at in fare info when applicable. Refuse stale known fares.
    fare=(info.get('fare') or {}); expires=fare.get('expires_at')
    if expires and time.time() >= float(expires): raise SafetyError('Guest Ride fare expired; estimate again and re-approve')
    payload=make_payload(u.get('guest'),pickup,dropoff,product['product_id'],fare_id,a.pickup_time)
    json_out(cli.create_guest_trip(payload,org,run))
if __name__=='__main__':main()
