"""Actual official SDK exercised with mocked HTTP, never network."""
import json
import httpx
import pytest
import groq_provider as g

def completion(text='Advice',reason='stop'):
 return {'choices':[{'message':{'content':text},'finish_reason':reason}]}

def install(monkeypatch,handler):
 original=g.GuardedTransport
 monkeypatch.setattr(g,'GuardedTransport',lambda:original(httpx.MockTransport(handler)))

def invoke():
 return g.GroqClient('LEAK_KEY').interactions.create(model='openai/gpt-oss-120b',input='fictional input',generation_config={'temperature':0.3,'max_output_tokens':4096})

def test_sdk_contract(monkeypatch):
 seen=[]
 def send(req):
  seen.append(req)
  assert str(req.url)==g.ENDPOINT and req.method=='POST'
  assert req.headers['authorization']=='Bearer LEAK_KEY'
  assert req.headers['user-agent'].startswith('Groq/Python ')
  assert req.headers['accept-encoding']=='identity'
  assert all(x==25 for x in req.extensions['timeout'].values())
  body=json.loads(req.content)
  assert body['response_format']=={'type':'json_object'} and body['reasoning_effort']=='low'
  return httpx.Response(200,json=completion())
 install(monkeypatch,send)
 assert invoke().output_text=='Advice' and len(seen)==1

@pytest.mark.parametrize('status,category',[(400,'request_failed'),(401,'access'),(403,'access'),(429,'rate_limit'),(500,'request_failed'),(302,'request_failed')])
def test_error_no_retry_redirect_or_leak(monkeypatch,status,category):
 calls=[]
 def send(req):
  calls.append(req)
  return httpx.Response(status,headers={'location':'https://evil.invalid/LEAK_KEY'},json={'error':{'message':'LEAK_BODY'}})
 install(monkeypatch,send)
 with pytest.raises(g.AIProviderError) as e:invoke()
 assert e.value.category==category and e.value.http_status==status
 assert 'LEAK' not in str(e.value) and len(calls)==1

@pytest.mark.parametrize('exc,category',[(httpx.ReadTimeout('LEAK_ERROR'),'timeout'),(httpx.ConnectError('LEAK_ERROR'),'network')])
def test_network_no_retry(monkeypatch,exc,category):
 calls=[]
 def send(req):calls.append(req);raise exc
 install(monkeypatch,send)
 with pytest.raises(g.AIProviderError) as e:invoke()
 assert e.value.category==category and 'LEAK' not in str(e.value) and len(calls)==1

@pytest.mark.parametrize('raw',[b'no json',b'{}',b'null',b'[]',json.dumps(completion('', 'stop')).encode(),json.dumps(completion('partial','length')).encode()])
def test_invalid_completion(monkeypatch,raw):
 install(monkeypatch,lambda req:httpx.Response(200,content=raw))
 with pytest.raises(g.AIProviderError) as e:invoke()
 assert e.value.category=='invalid_completion'

@pytest.mark.parametrize('status',[200,400,500])
def test_bounded_body_all_statuses(monkeypatch,status):
 install(monkeypatch,lambda req:httpx.Response(status,content=b'x'*(g.MAX_RESPONSE_BYTES+1)))
 with pytest.raises(g.AIProviderError) as e:invoke()
 assert e.value.category=='oversize'

def test_forbidden_destination_never_sent():
 calls=[]
 transport=g.GuardedTransport(httpx.MockTransport(lambda r:calls.append(r)))
 with pytest.raises(g.AIProviderError):transport.handle_request(httpx.Request('POST','https://evil.invalid'))
 assert not calls

def test_missing_key_no_transport(monkeypatch):
 monkeypatch.setattr(g,'GuardedTransport',lambda:pytest.fail('transport constructed'))
 with pytest.raises(g.AIProviderError) as e:g.GroqClient('').interactions.create(model='m',input='x')
 assert e.value.category=='missing_key'

def test_advice_no_json_flag(monkeypatch):
 def send(req):
  assert 'response_format' not in json.loads(req.content)
  return httpx.Response(200,json=completion())
 install(monkeypatch,send)
 assert g.GroqClient('dummy').interactions.create(model='m',input='x').output_text=='Advice'

def test_compression_refused_before_decode(monkeypatch):
 class Stream(httpx.SyncByteStream):
  def __iter__(self):pytest.fail('body consumed');yield b''
 install(monkeypatch,lambda req:httpx.Response(200,headers={'content-encoding':'gzip'},stream=Stream()))
 with pytest.raises(g.AIProviderError) as e:invoke()
 assert e.value.category=='invalid_completion'

def test_fixed_safe_categories():
 e=g.AIProviderError('LEAK',http_status='LEAK')
 assert e.category=='request_failed' and e.http_status is None and 'LEAK' not in str(e)

def test_env_headers_cannot_change_auth_or_identity(monkeypatch):
 monkeypatch.setenv('GROQ_CUSTOM_HEADERS','Authorization: LEAK_OTHER_KEY')
 monkeypatch.setattr(g,'GuardedTransport',lambda:pytest.fail('transport constructed'))
 with pytest.raises(g.AIProviderError) as e:invoke()
 assert e.value.category=='configuration' and 'LEAK' not in str(e.value)

def test_env_base_url_cannot_change_destination(monkeypatch):
 monkeypatch.setenv('GROQ_BASE_URL','https://evil.invalid')
 install(monkeypatch,lambda req:httpx.Response(200,json=completion()))
 assert invoke().output_text=='Advice'

def test_body_deadline_and_close():
 class Stream(httpx.SyncByteStream):
  closed=False
  def __iter__(self):yield b'x'
  def close(self):self.closed=True
 stream=Stream();bounded=g.BoundedStream(stream,0)
 with pytest.raises(g.AIProviderError) as e:list(bounded)
 bounded.close()
 assert e.value.category=='timeout' and stream.closed

def test_provider_debug_logs_disabled():
 import logging
 assert logging.getLogger('groq._base_client').disabled
