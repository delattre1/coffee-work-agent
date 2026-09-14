import sys,unittest,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from uber_api import UberClient

class Resp:
 def __init__(self,body=b'{}'): self.body=body
 def __enter__(self): return self
 def __exit__(self,*a): pass
 def read(self): return self.body
class Transport:
 def __init__(self): self.requests=[]
 def __call__(self,req): self.requests.append(req); return Resp()
class T(unittest.TestCase):
 def test_guest_estimate_scheduling_shape(self):
  t=Transport(); c=UberClient('secret','sandbox',transport=t); c.guest_estimates({'latitude':1,'longitude':2},{'latitude':3,'longitude':4},123)
  body=json.loads(t.requests[0].data); self.assertEqual(body['scheduling']['pickup_time'],123); self.assertNotIn('pickup_time',body)
 def test_rider_estimate_endpoint(self):
  t=Transport(); c=UberClient('secret','sandbox',transport=t); c.estimate('p',1,2,3,4)
  self.assertEqual(t.requests[0].full_url,'https://sandbox-api.uber.com/v1.2/requests/estimate')
 def test_no_bearer_in_repr_output_contract(self):
  t=Transport(); c=UberClient('secret','sandbox',transport=t); c.get_products(1,2)
  self.assertNotIn('secret',t.requests[0].full_url)
