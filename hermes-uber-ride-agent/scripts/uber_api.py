#!/usr/bin/env python3
from __future__ import annotations
import json,time,urllib.parse,urllib.request,urllib.error
from common import HermesError

class UberAPIError(HermesError):
    def __init__(self,status,message,body=None): super().__init__(message); self.status=status; self.body=body
class AmbiguousWriteError(UberAPIError): pass

class UberClient:
    def __init__(self,access_token,environment='sandbox',timeout=15,transport=None):
        self.base='https://sandbox-api.uber.com' if environment=='sandbox' else 'https://api.uber.com'; self.token=access_token; self.timeout=timeout; self.transport=transport or self._urlopen
    def _urlopen(self,req): return urllib.request.urlopen(req,timeout=self.timeout)
    def _call(self,method,path,params=None,json_body=None,extra_headers=None,retry_safe=True):
        url=self.base+path
        if params: url+='?'+urllib.parse.urlencode(params)
        body=json.dumps(json_body).encode() if json_body is not None else None
        headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json','Accept':'application/json'}
        if extra_headers: headers.update(extra_headers)
        req=urllib.request.Request(url,data=body,headers=headers,method=method)
        attempts=3 if retry_safe else 1
        for i in range(attempts):
            try:
                with self.transport(req) as r:
                    raw=r.read(); return json.loads(raw) if raw else None
            except urllib.error.HTTPError as e:
                raw=e.read().decode('utf-8','replace'); data=None
                try:data=json.loads(raw)
                except: data={'message':raw[:500]}
                if e.code in (502,503,504) and retry_safe and i+1<attempts: time.sleep(0.2*(2**i)); continue
                raise UberAPIError(e.code,f'Uber API HTTP {e.code}',data)
            except (TimeoutError,urllib.error.URLError) as e:
                if not retry_safe: raise AmbiguousWriteError(0,'network failure during non-idempotent Uber request; do not retry until request state is reconciled') from e
                if i+1<attempts: time.sleep(0.2*(2**i)); continue
                raise UberAPIError(0,'Uber network error') from e
    def get_me(self): return self._call('GET','/v1.2/me')
    def get_products(self,latitude,longitude): return self._call('GET','/v1.2/products',{'latitude':latitude,'longitude':longitude})
    def estimate(self,product_id,start_latitude,start_longitude,end_latitude,end_longitude):
        return self._call('POST','/v1.2/requests/estimate',json_body={'product_id':product_id,'start_latitude':start_latitude,'start_longitude':start_longitude,'end_latitude':end_latitude,'end_longitude':end_longitude},retry_safe=True)
    def request_ride(self,payload): return self._call('POST','/v1.2/requests',json_body=payload,retry_safe=False)
    def get_request(self,request_id): return self._call('GET',f'/v1.2/requests/{urllib.parse.quote(request_id,safe="")}')
    def cancel_request(self,request_id): return self._call('DELETE',f'/v1.2/requests/{urllib.parse.quote(request_id,safe="")}',retry_safe=False)
    def sandbox_set_status(self,request_id,status):
        allowed={'processing','accepted','arriving','in_progress','completed','driver_canceled'}
        if status not in allowed: raise ValueError('invalid sandbox status')
        return self._call('PUT',f'/v1.2/sandbox/requests/{urllib.parse.quote(request_id,safe="")}',json_body={'status':status},retry_safe=True)
    def guest_estimates(self,pickup,dropoff,pickup_time_ms=None,organization_uuid=None,sandbox_run_uuid=None):
        payload={'pickup':pickup,'dropoff':dropoff}
        if pickup_time_ms is not None: payload['scheduling']={'pickup_time':pickup_time_ms}
        h={}
        if organization_uuid:h['x-uber-organizationuuid']=organization_uuid
        if sandbox_run_uuid:h['x-uber-sandbox-runuuid']=sandbox_run_uuid
        return self._call('POST','/v1/guests/trips/estimates',json_body=payload,extra_headers=h,retry_safe=True)
    def create_guest_trip(self,payload,organization_uuid=None,sandbox_run_uuid=None):
        h={}
        if organization_uuid:h['x-uber-organizationuuid']=organization_uuid
        if sandbox_run_uuid:h['x-uber-sandbox-runuuid']=sandbox_run_uuid
        return self._call('POST','/v1/guests/trips',json_body=payload,extra_headers=h,retry_safe=False)
