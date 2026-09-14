#!/usr/bin/env python3
from __future__ import annotations
import argparse,re
from common import load_config, timezone_name, json_out
from ride_state import resolve_when

ALIASES={
 'casa':['casa','minha casa'], 'work':['trabalho','escritório','escritorio'],
 'airport':['aeroporto'], 'calendar':['minha reunião','minha reuniao','meu próximo compromisso','meu proximo compromisso']}

def _loc_fragment(text:str, keyword:str):
    m=re.search(keyword+r'\s+(.+?)(?=\s+(?:às|as|amanh[ãa]|hoje|daqui|em\s+\d+)|[.!?]|$)',text,re.I)
    return m.group(1).strip(' ,') if m else None

def parse(text:str,tz:str,now=None)->dict:
    low=' '.join(text.strip().split())
    if not (re.search(r'\b(uber|corrida|carro)\b',low,re.I) or re.search(r'\b(me busca|me leva|chama(?:r)? um carro)\b',low,re.I)):
        return {'intent':'unknown','confidence':0.0}
    when=resolve_when(low,tz,now)
    pickup={'mode':'current_location'}
    destination=None
    m=re.search(r'\bme busca em\s+(.+?)(?:\s+(?:às|as)\s+\d{1,2}(?::\d{2})?\s*)?\s+e\s+me leva (?:ao|à|a|para)\s+(.+?)(?=\s+(?:às|as|amanh[ãa]|hoje|daqui)|[.!?]|$)',low,re.I)
    if m:
        pickup={'mode':'named','query':m.group(1).strip()}; destination={'mode':'named','query':m.group(2).strip()}
    else:
        for canonical,words in ALIASES.items():
            if any(re.search(r'\b'+re.escape(w)+r'\b',low,re.I) for w in words):
                if canonical=='calendar': destination={'mode':'calendar'}
                elif canonical=='casa' and re.search(r'\b(?:para|pro|pra)\s+(?:minha\s+)?casa\b',low,re.I): destination={'mode':'named','query':'casa'}
                elif canonical=='work' and re.search(r'\b(?:para|pro|pra|ao)\s+(?:o\s+)?(?:trabalho|escritório|escritorio)\b',low,re.I): destination={'mode':'named','query':'trabalho'}
                elif canonical=='airport' and re.search(r'\b(?:para|pro|pra|ao)\s+(?:o\s+)?aeroporto\b',low,re.I): destination={'mode':'named','query':'aeroporto'}
        if destination is None:
            frag=_loc_fragment(low,r'\b(?:para|até|ate)\b')
            if frag and not re.fullmatch(r'(?:as|às)?\s*\d{1,2}(?::\d{2})?\s*h?',frag,re.I): destination={'mode':'explicit','query':frag}
    return {'intent':'ride','when':when,'pickup':pickup,'destination':destination,'confidence':0.95 if destination else 0.82}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('text'); ap.add_argument('--config'); args=ap.parse_args()
    cfg=load_config(args.config); json_out(parse(args.text,timezone_name(cfg)))
if __name__=='__main__': main()
