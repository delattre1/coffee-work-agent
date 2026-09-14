#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,uuid
from common import load_config,json_out,assert_environment_safe
from parse_ride_request import parse
from resolve_ride_context import resolve
from ride_state import Approval
from common import timezone_name

def prepare(text,cfg):
    p=parse(text,timezone_name(cfg));
    if p.get('intent')!='ride': return {'state':'FAILED','reason':'not_ride_intent'}
    if p['when'].get('kind')=='clarify': return {'state':'PARSED','needs_clarification':p['when']}
    ctx=resolve(p,cfg)
    if not ctx.get('pickup'): return {'state':'PARSED','needs':'pickup_location','parsed':p}
    if not ctx.get('destination'): return {'state':'PARSED','needs':'destination','parsed':p,'pickup':ctx['pickup']}
    return {'ride_id':str(uuid.uuid4()),'state':'CONTEXT_RESOLVED','parsed':p,'pickup':ctx['pickup'],'destination':ctx['destination'],'approval':Approval().asdict()}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--config'); ap.add_argument('--environment'); ap.add_argument('text'); args=ap.parse_args(); cfg=load_config(args.config); assert_environment_safe(cfg,args.environment); json_out(prepare(args.text,cfg))
if __name__=='__main__':main()
