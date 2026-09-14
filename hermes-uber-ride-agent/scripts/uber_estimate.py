#!/usr/bin/env python3
from __future__ import annotations
import argparse,os
from common import load_config,assert_environment_safe,json_out,uber_config
from uber_oauth import config_values,refresh_access_token
from uber_tokens import get_valid_access_token
from uber_api import UberClient

def select_product(products,preferred,fallbacks=()):
    rows=products.get('products') or []
    names=[preferred,*fallbacks]
    for wanted in names:
        for p in rows:
            if wanted and wanted.lower() in {str(p.get('display_name','')).lower(),str(p.get('short_description','')).lower(),str(p.get('product_group','')).lower()}:
                return p
    return rows[0] if rows else None

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--config'); ap.add_argument('--environment'); ap.add_argument('--user-id',default='owner'); ap.add_argument('--start-lat',type=float,required=True); ap.add_argument('--start-lon',type=float,required=True); ap.add_argument('--end-lat',type=float,required=True); ap.add_argument('--end-lon',type=float,required=True); args=ap.parse_args()
    cfg=load_config(args.config); env=assert_environment_safe(cfg,args.environment); cid,secret,_,_=config_values(cfg)
    tok=get_valid_access_token(args.user_id,lambda rt: refresh_access_token(cid,secret,rt)); c=UberClient(tok,env); u=uber_config(cfg)
    p=select_product(c.get_products(args.start_lat,args.start_lon),u.get('default_product'),u.get('product_fallbacks',[]))
    if not p: raise SystemExit('no Uber products returned for pickup location')
    est=c.estimate(p['product_id'],args.start_lat,args.start_lon,args.end_lat,args.end_lon)
    if est.get('pickup_estimate') is None: raise SystemExit('no drivers available: pickup_estimate is null')
    fare=est.get('fare') or {}
    if not fare.get('fare_id'): raise SystemExit('estimate did not return fare_id')
    json_out({'product':p,'estimate':est})
if __name__=='__main__':main()
