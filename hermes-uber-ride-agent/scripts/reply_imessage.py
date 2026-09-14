#!/usr/bin/env python3
from __future__ import annotations
import argparse,subprocess
from common import load_config,ConfigError

def send_message(cfg,text):
    p=((cfg.get('uber') or {}).get('imessage_provider') or {}); argv=p.get('argv')
    if not (isinstance(argv,list) and argv and all(isinstance(x,str) for x in argv)):
        raise ConfigError('uber.imessage_provider.argv is not configured; point it at the existing shared iMessage helper')
    cp=subprocess.run([*argv,'--message',text],capture_output=True,text=True,timeout=15)
    if cp.returncode: raise RuntimeError('iMessage provider failed')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--config'); ap.add_argument('message'); args=ap.parse_args(); send_message(load_config(args.config),args.message)
if __name__=='__main__':main()
