import sys,unittest
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from parse_ride_request import parse
class T(unittest.TestCase):
 def setUp(self): self.now=datetime(2026,9,3,11,5,tzinfo=ZoneInfo('America/Sao_Paulo'))
 def test_office(self):
  p=parse('Hermes, chama um Uber para o escritório às 14h.','America/Sao_Paulo',self.now); self.assertEqual(p['destination']['query'],'trabalho')
 def test_airport(self):
  p=parse('Hermes, chama um Uber para o aeroporto às 06:00 amanhã.','America/Sao_Paulo',self.now); self.assertEqual(p['destination']['query'],'aeroporto')
 def test_pickup_drop(self):
  p=parse('Hermes, me busca em casa às 18:30 e me leva ao aeroporto.','America/Sao_Paulo',self.now); self.assertEqual(p['pickup']['query'],'casa'); self.assertEqual(p['destination']['query'],'aeroporto')
 def test_no_destination(self): self.assertIsNone(parse('Hermes, chama um Uber agora.','America/Sao_Paulo',self.now)['destination'])
