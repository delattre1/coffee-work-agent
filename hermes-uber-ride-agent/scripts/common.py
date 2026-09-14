#!/usr/bin/env python3
from __future__ import annotations
import json, os, sys
from pathlib import Path

class HermesError(RuntimeError): pass
class ConfigError(HermesError): pass
class SafetyError(HermesError): pass

SECRET_KEYS={"client_secret","access_token","refresh_token","authorization_code","code"}

def eprint(*a): print(*a,file=sys.stderr)

def load_config(path: str|None=None)->dict:
    p=Path(path or os.getenv("HERMES_CONFIG","/opt/data/ld/config.json"))
    if not p.exists(): raise ConfigError(f"configuration not found: {p}")
    with p.open(encoding='utf-8') as f: cfg=json.load(f)
    if not isinstance(cfg,dict): raise ConfigError("configuration root must be an object")
    return cfg

def uber_config(cfg:dict)->dict:
    u=cfg.get("uber")
    if not isinstance(u,dict): raise ConfigError("uber configuration missing")
    return u

def timezone_name(cfg:dict)->str:
    tz=((cfg.get('family') or {}).get('timezone'))
    if not tz: raise ConfigError('family.timezone missing')
    return str(tz)

def env_value(name:str, required=True)->str|None:
    v=os.getenv(name)
    if required and not v: raise ConfigError(f"environment variable {name} is required")
    return v

def assert_environment_safe(cfg:dict, requested:str|None=None)->str:
    u=uber_config(cfg)
    env=(requested or os.getenv('HERMES_UBER_ENV') or u.get('environment') or 'sandbox').lower()
    if env not in {'sandbox','production'}: raise ConfigError('uber.environment must be sandbox or production')
    if env=='production':
        if os.getenv('HERMES_UBER_ENV')!='production': raise SafetyError('production requires HERMES_UBER_ENV=production')
        if os.getenv('HERMES_ALLOW_REAL_RIDES','').lower()!='true': raise SafetyError('production requires HERMES_ALLOW_REAL_RIDES=true')
        approval=(u.get('approval') or {})
        if approval.get('required') is not True: raise SafetyError('production requires uber.approval.required=true')
    return env

def redact(obj):
    if isinstance(obj,dict):
        return {k: ('<redacted>' if k.lower() in SECRET_KEYS else redact(v)) for k,v in obj.items()}
    if isinstance(obj,list): return [redact(x) for x in obj]
    return obj

def json_out(obj):
    json.dump(obj,sys.stdout,ensure_ascii=False,sort_keys=True)
    print()
