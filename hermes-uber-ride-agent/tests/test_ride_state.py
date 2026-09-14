import sys,unittest
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from ride_state import resolve_when
class T(unittest.TestCase):
 def setUp(self): self.now=datetime(2026,9,3,11,5,tzinfo=ZoneInfo('America/Sao_Paulo'))
 def test_now(self): self.assertEqual(resolve_when('Uber agora','America/Sao_Paulo',self.now)['kind'],'immediate')
 def test_14(self): self.assertEqual(resolve_when('Uber às 14h','America/Sao_Paulo',self.now)['time'],'14:00')
 def test_today_past(self): self.assertEqual(resolve_when('Uber hoje às 10h','America/Sao_Paulo',self.now)['reason'],'today_time_already_passed')
 def test_bare_past(self): self.assertEqual(resolve_when('Uber às 10h','America/Sao_Paulo',self.now)['kind'],'clarify')
 def test_tomorrow(self): self.assertEqual(resolve_when('Uber amanhã às 14h','America/Sao_Paulo',self.now)['date'],'2026-09-04')
 def test_relative(self): self.assertEqual(resolve_when('Uber daqui 30 minutos','America/Sao_Paulo',self.now)['time'],'11:35')
