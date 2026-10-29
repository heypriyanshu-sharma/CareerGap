"""Strict application output validation using fictional responses, offline."""
import asyncio
import json
from types import SimpleNamespace
import pytest
import backend

def fake(monkeypatch,data):
    client=SimpleNamespace(interactions=SimpleNamespace(create=lambda **kw:SimpleNamespace(output_text=json.dumps(data))))
    monkeypatch.setattr(backend,'build_client',lambda:client)

def question_data(mode):
    return {'questions':[{'type':kind,'text':f'{kind} fictional question {i}'} for kind,n in backend.INTERVIEW_QUESTION_CONFIG[mode].items() for i in range(n)]}

@pytest.mark.parametrize('mode',['quick','full'])
def test_exact_distribution(monkeypatch,mode):
    fake(monkeypatch,question_data(mode))
    q=asyncio.run(backend.generate_interview_questions(mode,None,'dummy','dummy',[]))
    assert len(q)==sum(backend.INTERVIEW_QUESTION_CONFIG[mode].values())

@pytest.mark.parametrize('change',['missing','extra','wrong_type','blank'])
def test_bad_questions(monkeypatch,change):
    d=question_data('quick')
    if change=='missing':d['questions'].pop()
    if change=='extra':d['questions'].append(d['questions'][0])
    if change=='wrong_type':d['questions'][0]['type']='project'
    if change=='blank':d['questions'][0]['text']='  '
    fake(monkeypatch,d)
    with pytest.raises(RuntimeError):asyncio.run(backend.generate_interview_questions('quick',None,'dummy','dummy',[]))

def feedback():
    return {'score':75,'feedback':{k:{'score':75,'strengths':['Dummy strength'],'gaps':['Dummy gap']} for k in ['technical','behavioral','project']},'weak_areas':['Dummy area'],'recommendations':[{'area':'Testing','action':'Write one dummy test','resources':[]}]}

def test_feedback_valid(monkeypatch):
    d=feedback();fake(monkeypatch,d)
    assert asyncio.run(backend.evaluate_interview_answers('quick',None,'dummy','dummy',[],[],[]))==d

@pytest.mark.parametrize('change',['score_high','category_missing','category_high','recommendation_missing','recommendation_blank','wrong_weak_type','extra'])
def test_feedback_rejected_before_persistence(monkeypatch,change):
    d=feedback()
    if change=='score_high':d['score']=101
    if change=='category_missing':d['feedback'].pop('project')
    if change=='category_high':d['feedback']['project']['score']=-1
    if change=='recommendation_missing':d['recommendations']=[{'area':'Testing'}]
    if change=='recommendation_blank':d['recommendations'][0]['action']=''
    if change=='wrong_weak_type':d['weak_areas']='not a list'
    if change=='extra':d['unexpected']='bad'
    fake(monkeypatch,d)
    with pytest.raises(RuntimeError):asyncio.run(backend.evaluate_interview_answers('quick',None,'dummy','dummy',[],[],[]))

@pytest.mark.parametrize('operation',['questions','feedback'])
def test_typed_provider_failure_preserved(monkeypatch,operation):
 from groq_provider import AIProviderError
 def failure(**kw):raise AIProviderError('rate_limit',429)
 client=SimpleNamespace(interactions=SimpleNamespace(create=failure))
 monkeypatch.setattr(backend,'build_client',lambda:client)
 with pytest.raises(AIProviderError) as e:
  if operation=='questions':asyncio.run(backend.generate_interview_questions('quick',None,'dummy','dummy',[]))
  else:asyncio.run(backend.evaluate_interview_answers('quick',None,'dummy','dummy',[],[],[]))
 assert e.value.category=='rate_limit' and e.value.http_status==429

def test_legacy_and_new_keys_redacted(monkeypatch):
 from ai_advisor import safe_error_detail
 monkeypatch.setenv('GEMINI_API_KEY','legacy-secret')
 monkeypatch.setenv('GROQ_API_KEY','new-secret')
 assert safe_error_detail(ValueError('legacy-secret new-secret'))=='[redacted] [redacted]'
