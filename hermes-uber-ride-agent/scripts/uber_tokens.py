#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, time
from common import HermesError
SERVICE='com.hermes.uber'

class TokenStoreError(HermesError): pass

def _security(args,input_text=None):
    try:
        return subprocess.run(['/usr/bin/security',*args],input=input_text,text=True,capture_output=True,check=True).stdout
    except FileNotFoundError as e: raise TokenStoreError('macOS security command unavailable') from e
    except subprocess.CalledProcessError as e: raise TokenStoreError('Keychain operation failed') from e

def save_tokens(user_id:str,tokens:dict):
    clean={k:tokens.get(k) for k in ('access_token','refresh_token','expires_in','scope','token_type') if tokens.get(k) is not None}
    if not clean.get('access_token'): raise TokenStoreError('access_token missing')
    clean['saved_at']=int(time.time())
    payload=json.dumps(clean,separators=(',',':'))
    subprocess.run(['/usr/bin/security','delete-generic-password','-s',SERVICE,'-a',user_id],capture_output=True,text=True)
    _security(['add-generic-password','-U','-s',SERVICE,'-a',user_id,'-w',payload])

def load_tokens(user_id:str)->dict:
    raw=_security(['find-generic-password','-s',SERVICE,'-a',user_id,'-w']).strip()
    try: return json.loads(raw)
    except Exception as e: raise TokenStoreError('invalid token payload in Keychain') from e

def delete_tokens(user_id:str):
    try: _security(['delete-generic-password','-s',SERVICE,'-a',user_id])
    except TokenStoreError: pass

def token_exists(user_id:str)->bool:
    try: load_tokens(user_id); return True
    except TokenStoreError: return False

def token_expired(t:dict,skew=60)->bool:
    return bool(t.get('expires_in')) and time.time() >= int(t.get('saved_at',0))+int(t['expires_in'])-skew

def get_valid_access_token(user_id:str,refresh_fn):
    t=load_tokens(user_id)
    if token_expired(t):
        rt=t.get('refresh_token')
        if not rt: raise TokenStoreError('token expired and no refresh_token is available')
        t=refresh_fn(rt); save_tokens(user_id,t)
    return t['access_token']
