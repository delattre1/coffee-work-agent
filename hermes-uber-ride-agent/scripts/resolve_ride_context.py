#!/usr/bin/env python3
from __future__ import annotations
import os,re,subprocess,json
from common import ConfigError

def _coord(lat,lon,address=None,source='config'):
    if lat is None or lon is None: return None
    return {'latitude':float(lat),'longitude':float(lon),'address':address,'source':source}

def configured_place(cfg,name):
    places=((cfg.get('uber') or {}).get('places') or {})
    p=places.get(name)
    if isinstance(p,dict) and p.get('latitude') is not None and p.get('longitude') is not None:
        return _coord(p['latitude'],p['longitude'],p.get('address'),'config')
    prefix={'casa':'HOME','home':'HOME','trabalho':'WORK','work':'WORK','escritório':'WORK','escritorio':'WORK'}.get(name.lower())
    if prefix:
        lat=os.getenv(prefix+'_LAT'); lon=os.getenv(prefix+'_LON'); addr=os.getenv(prefix+'_ADDRESS')
        if lat and lon:return _coord(lat,lon,addr,'environment')
    return None

def get_current_location(cfg):
    u=cfg.get('uber') or {}; p=(u.get('pickup') or {})
    if p.get('mode')=='configured':
        name=p.get('place','home'); loc=configured_place(cfg,name)
        if loc:return loc
    provider=(u.get('location_provider') or {})
    argv=provider.get('argv')
    if isinstance(argv,list) and argv and all(isinstance(x,str) for x in argv):
        cp=subprocess.run(argv,capture_output=True,text=True,timeout=10,check=True); d=json.loads(cp.stdout)
        return _coord(d.get('latitude'),d.get('longitude'),d.get('address'),'location_provider')
    return None

def resolve_calendar_destination(cfg,when):
    cal=((cfg.get('uber') or {}).get('calendar_provider') or {}); argv=cal.get('argv')
    if not (isinstance(argv,list) and argv and all(isinstance(x,str) for x in argv)): return None
    cp=subprocess.run([*argv,'--when',when['datetime']],capture_output=True,text=True,timeout=15,check=True); d=json.loads(cp.stdout)
    if d.get('latitude') is None or d.get('longitude') is None:return None
    return _coord(d['latitude'],d['longitude'],d.get('address'),'calendar')

def resolve_named(cfg,query):
    q=query.lower().strip()
    for n in ('home','casa','work','trabalho','escritório','escritorio','airport','aeroporto'):
        if q==n or n in q:
            loc=configured_place(cfg,n)
            if loc:return loc
    geocoder=((cfg.get('uber') or {}).get('geocoder_provider') or {}); argv=geocoder.get('argv')
    if isinstance(argv,list) and argv and all(isinstance(x,str) for x in argv):
        cp=subprocess.run([*argv,'--query',query],capture_output=True,text=True,timeout=15,check=True); d=json.loads(cp.stdout)
        if d.get('latitude') is not None and d.get('longitude') is not None:return _coord(d['latitude'],d['longitude'],d.get('address'),'explicit')
    return None

def resolve(parsed,cfg):
    pickup=parsed.get('pickup') or {'mode':'current_location'}
    if pickup.get('mode')=='current_location': p=get_current_location(cfg)
    else:p=resolve_named(cfg,pickup.get('query',''))
    dest=parsed.get('destination'); d=None
    if dest:
        d=resolve_calendar_destination(cfg,parsed['when']) if dest.get('mode')=='calendar' else resolve_named(cfg,dest.get('query',''))
    return {'pickup':p,'destination':d}
