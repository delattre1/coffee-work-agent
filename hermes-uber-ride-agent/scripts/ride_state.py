#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re

STATES=('RECEIVED','PARSED','CONTEXT_RESOLVED','AUTH_REQUIRED','AUTHENTICATED','PRODUCT_SELECTED','ESTIMATE_READY','AWAITING_APPROVAL','APPROVED','REQUESTING','SCHEDULED','REQUESTED','DRIVER_ASSIGNED','DRIVER_ARRIVING','IN_PROGRESS','COMPLETED','CANCELED','FAILED')

@dataclass
class Approval:
    approved: bool=False
    approved_at: str|None=None
    fare_id: str|None=None
    quoted_amount: float|None=None
    currency: str|None=None
    pickup: dict|None=None
    destination: dict|None=None
    product_id: str|None=None
    def asdict(self): return asdict(self)

_TIME_PATTERNS=[
 re.compile(r'(?<!\d)(\d{1,2})(?::(\d{2}))?\s*h\b',re.I),
 re.compile(r'(?<!\d)(\d{1,2}):(\d{2})(?!\d)'),
 re.compile(r'(?<!\d)(\d{1,2})\s*(am|pm)\b',re.I),
]

def _clock(text):
    for rx in _TIME_PATTERNS:
        m=rx.search(text)
        if not m: continue
        h=int(m.group(1)); mins=int(m.group(2) or 0) if rx is not _TIME_PATTERNS[2] else 0
        if rx is _TIME_PATTERNS[2]:
            ap=m.group(2).lower(); h=(h%12)+(12 if ap=='pm' else 0)
        if 0<=h<=23 and 0<=mins<=59: return h,mins
    m=re.search(r'\b(?:às|as|para)\s+(\d{1,2})(?![\d:])',text,re.I)
    if m:
        h=int(m.group(1));
        if 0<=h<=23: return h,0
    return None

def resolve_when(text:str,tz_name:str,now:datetime|None=None,past_policy='clarify')->dict:
    tz=ZoneInfo(tz_name); now=(now.astimezone(tz) if now else datetime.now(tz))
    low=text.lower().strip()
    if re.search(r'\b(agora|já|ja)\b',low):
        return {'kind':'immediate','datetime':now.isoformat(),'timezone':tz_name}
    m=re.search(r'\b(?:daqui a|daqui|em)\s+(\d+)\s*(minuto|minutos|min)\b',low)
    if m:
        dt=now+timedelta(minutes=int(m.group(1))); return {'kind':'scheduled','datetime':dt.isoformat(),'date':dt.date().isoformat(),'time':dt.strftime('%H:%M'),'timezone':tz_name}
    m=re.search(r'\b(?:daqui a|daqui|em)\s+(\d+)\s*(hora|horas|h)\b',low)
    if m:
        dt=now+timedelta(hours=int(m.group(1))); return {'kind':'scheduled','datetime':dt.isoformat(),'date':dt.date().isoformat(),'time':dt.strftime('%H:%M'),'timezone':tz_name}
    clock=_clock(low)
    if not clock:
        return {'kind':'immediate','datetime':now.isoformat(),'timezone':tz_name} if 'uber' in low else {'kind':'unspecified','timezone':tz_name}
    h,mi=clock
    explicit_today=bool(re.search(r'\bhoje\b',low)); explicit_tomorrow=bool(re.search(r'\bamanh[ãa]\b',low))
    day=now.date()+timedelta(days=1 if explicit_tomorrow else 0)
    dt=datetime(day.year,day.month,day.day,h,mi,tzinfo=tz)
    if not explicit_today and not explicit_tomorrow and dt<=now:
        if past_policy=='tomorrow': dt+=timedelta(days=1)
        else: return {'kind':'clarify','reason':'time_already_passed','requested_time':f'{h:02d}:{mi:02d}','timezone':tz_name}
    if explicit_today and dt<=now:
        return {'kind':'clarify','reason':'today_time_already_passed','requested_time':f'{h:02d}:{mi:02d}','timezone':tz_name}
    return {'kind':'scheduled','datetime':dt.isoformat(),'date':dt.date().isoformat(),'time':dt.strftime('%H:%M'),'timezone':tz_name}

def epoch_ms(iso_datetime:str)->int:
    return int(datetime.fromisoformat(iso_datetime).timestamp()*1000)
