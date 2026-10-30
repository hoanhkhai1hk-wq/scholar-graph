"""Test-only ASGI instrumentation. No bodies, query text, headers or credentials."""
import json
import threading
import time
import os
from scholar_graph.api import create_app

if os.environ.get('SG_ITEM08_VALIDATION_FAULT') == 'true':
    # Deliberately invalid model output, isolated from the real provider. Only a
    # dummy key exists in this container; no credential leaves the process.
    import httpx
    from scholar_graph.deepseek_client import DeepSeekClient
    def invalid_translation(request):
        content=json.dumps({'translations':[],'terminology':[]})
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':content}}]})
    DeepSeekClient.environment=classmethod(lambda cls:cls(key='fault-injection-only',model='fault-model',transport=httpx.MockTransport(invalid_translation)))

application=create_app()
rows=[]
lock=threading.Lock()

async def app(scope,receive,send):
    if scope['type']!='http':return await application(scope,receive,send)
    if scope['path']=='/__item08/requests':
        with lock:
            if scope['method']=='POST':rows.clear()
            value=list(rows)
        body=json.dumps(value).encode()
        await send({'type':'http.response.start','status':200,'headers':[(b'content-type',b'application/json')]})
        return await send({'type':'http.response.body','body':body})
    started=time.perf_counter();status=0;size=0
    async def wrapped(message):
        nonlocal status,size
        if message['type']=='http.response.start':status=message['status']
        elif message['type']=='http.response.body':size+=len(message.get('body',b''))
        await send(message)
    try:await application(scope,receive,wrapped)
    finally:
        with lock:rows.append({'method':scope['method'],'path':scope['path'],'status':status,'bytes':size,'ms':round((time.perf_counter()-started)*1000,3)})
