import sys,unittest,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from common import assert_environment_safe,SafetyError
from uber_oauth import handle_callback
from uber_request import approval_matches
class T(unittest.TestCase):
 def test_oauth_state_mismatch(self):
  with self.assertRaises(ValueError): handle_callback('code=x&state=bad','good')
 def test_production_gate(self):
  cfg={'uber':{'environment':'production','approval':{'required':True}}}
  old=dict(os.environ)
  try:
   os.environ.pop('HERMES_ALLOW_REAL_RIDES',None); os.environ['HERMES_UBER_ENV']='production'
   with self.assertRaises(SafetyError): assert_environment_safe(cfg)
  finally: os.environ.clear(); os.environ.update(old)
 def test_approval_bound_to_fare(self):
  payload={'product_id':'p','start_latitude':1,'start_longitude':2,'end_latitude':3,'end_longitude':4}
  good={'approved':True,'fare_id':'f','product_id':'p','pickup':{'latitude':1,'longitude':2},'destination':{'latitude':3,'longitude':4}}
  self.assertTrue(approval_matches(good,payload,{'fare':{'fare_id':'f'}}))
  bad=dict(good); bad['destination']={'latitude':9,'longitude':4}
  self.assertFalse(approval_matches(bad,payload,{'fare':{'fare_id':'f'}}))

class GuestAuthT(unittest.TestCase):
 def test_guest_token_is_separate_account(self):
  import uber_schedule
  self.assertEqual(uber_schedule.GUEST_TOKEN_ACCOUNT,'guest-rides-app')
