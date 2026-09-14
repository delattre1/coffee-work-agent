#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, secrets, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from common import load_config, uber_config, env_value, json_out, ConfigError
from uber_tokens import save_tokens
AUTH='https://auth.uber.com/oauth/v2/authorize'; TOKEN='https://auth.uber.com/oauth/v2/token'

def generate_state()->str: return secrets.token_urlsafe(32)
def build_authorization_url(client_id,redirect_uri,scopes,state):
    if not state: raise ValueError('state required')
    q=urllib.parse.urlencode({'response_type':'code','client_id':client_id,'scope':' '.join(scopes),'redirect_uri':redirect_uri,'state':state})
    return AUTH+'?'+q

def _token_post(data):
    body=urllib.parse.urlencode(data).encode(); req=urllib.request.Request(TOKEN,data=body,headers={'Content-Type':'application/x-www-form-urlencoded'},method='POST')
    with urllib.request.urlopen(req,timeout=20) as r: return json.loads(r.read())
def exchange_code_for_token(client_id,client_secret,redirect_uri,code):
    return _token_post({'client_id':client_id,'client_secret':client_secret,'grant_type':'authorization_code','redirect_uri':redirect_uri,'code':code})
def refresh_access_token(client_id,client_secret,refresh_token):
    return _token_post({'client_id':client_id,'client_secret':client_secret,'grant_type':'refresh_token','refresh_token':refresh_token})
def client_credentials_token(client_id,client_secret,scope='guests.trips'):
    return _token_post({'client_id':client_id,'client_secret':client_secret,'grant_type':'client_credentials','scope':scope})
def handle_callback(query,expected_state):
    p=urllib.parse.parse_qs(query,strict_parsing=True); state=(p.get('state') or [None])[0]; code=(p.get('code') or [None])[0]
    if not state or not secrets.compare_digest(state,expected_state): raise ValueError('OAuth state mismatch')
    if not code: raise ValueError('authorization code missing')
    return code

def config_values(cfg):
    u=uber_config(cfg); cid=os.getenv('HERMES_UBER_CLIENT_ID') or u.get('client_id'); redirect=os.getenv('HERMES_UBER_REDIRECT_URI') or u.get('redirect_uri')
    if not cid or not redirect: raise ConfigError('Uber client_id/redirect_uri missing')
    secret=env_value(u.get('client_secret_env','HERMES_UBER_CLIENT_SECRET'))
    scopes=u.get('scopes') or ['request','profile']
    return cid,secret,redirect,scopes

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--config'); ap.add_argument('--user-id',default='owner'); ap.add_argument('--print-url',action='store_true'); args=ap.parse_args()
    cfg=load_config(args.config); cid,secret,redirect,scopes=config_values(cfg); state=generate_state(); url=build_authorization_url(cid,redirect,scopes,state)
    if args.print_url: print(url); return
    parsed=urllib.parse.urlparse(redirect)
    if parsed.hostname not in {'127.0.0.1','localhost'}: raise ConfigError('automatic callback server supports localhost only; use --print-url for public HTTPS callback')
    port=parsed.port or (443 if parsed.scheme=='https' else 80); path=parsed.path
    result={}
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            u=urllib.parse.urlparse(self.path)
            if u.path!=path: self.send_response(404); self.end_headers(); return
            try:
                code=handle_callback(u.query,state); tokens=exchange_code_for_token(cid,secret,redirect,code); save_tokens(args.user_id,tokens); result['ok']=True
                self.send_response(200); self.send_header('Content-Type','text/plain; charset=utf-8'); self.end_headers(); self.wfile.write(b'Uber conectado com sucesso. Pode fechar esta janela.')
            except Exception: result['ok']=False; self.send_response(400); self.end_headers(); self.wfile.write(b'Falha na autorizacao Uber.')
        def log_message(self,*a): pass
    print(url)
    server=HTTPServer((parsed.hostname,port),H); server.handle_request()
    if not result.get('ok'): raise SystemExit(2)
if __name__=='__main__': main()
