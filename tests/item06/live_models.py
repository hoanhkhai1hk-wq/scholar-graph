"""Real configured-provider generation and native-Chinese translation, without mocks."""
import argparse,json,re,time,subprocess,sys,base64,unicodedata
from common import ROOT,BASE,write,client,ready,wait_task
from baseline import IDEA
sys.path.insert(0,str(ROOT/'backend'))
from scholar_graph.translation import check_numbers,check_terms,protect
EXPECTED={
 '1706.03762':{'title':'Attention Is All You Need','year':2017,'authors':['Ashish Vaswani','Noam Shazeer','Niki Parmar','Jakob Uszkoreit','Llion Jones','Aidan N. Gomez','Łukasz Kaiser','Illia Polosukhin']},
 '2106.09685':{'title':'LoRA: Low-Rank Adaptation of Large Language Models','year':2021,'authors':['Edward Hu','Yelong Shen','Phillip Wallis','Zeyuan Allen-Zhu','Yuanzhi Li','Shean Wang','Lu Wang','Weizhu Chen']},
 '2203.02155':{'title':'Training language models to follow instructions with human feedback','year':2022,'authors':['Long Ouyang','Jeff Wu','Xu Jiang','Diogo Almeida','Carroll L. Wainwright','Pamela Mishkin','Chong Zhang','Sandhini Agarwal','Katarina Slama','Alex Ray','John Schulman','Jacob Hilton','Fraser Kelton','Luke Miller','Maddie Simens','Amanda Askell','Peter Welinder','Paul Christiano','Jan Leike','Ryan Lowe']}}
def key(text):return ''.join(c.lower() for c in unicodedata.normalize('NFKD',text.replace('Ł','L').replace('ł','l')) if c.isalnum())
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args();out=BASE/a.run;out.mkdir(exist_ok=False)
    papers=json.loads((BASE/'selected-papers.json').read_text(encoding='utf8'));ids=[p['paper_id'] for p in papers];report={'cases':[]}
    def record(row):report['cases'].append(row);write(out/'results.json',report);print(json.dumps(row,ensure_ascii=False),flush=True)
    with client() as c:
        ready(c)
        for kind,scope,idea in [('outline',ids,IDEA),('topology',[ids[0]],'从Attention原文提取Transformer方法逻辑，包括输入、嵌入、位置编码、编码器、解码器、输出之间的真实依赖。不要用章节顺序冒充方法关系。')]:
            start=time.monotonic();r=c.post('/api/v2/writing/tasks',json={'paper_ids':scope,'kind':kind,'idea':idea});r.raise_for_status();t=wait_task(c,r.json(),out/(kind+'-task.json'))
            row={'case':kind,'task_id':t['id'],'status':t['status'],'seconds':round(time.monotonic()-start,3),'error':t.get('error')}
            if t['status']=='completed':
                result=t['result'];row['model_calls']=len(result['metadata']['model_calls'])
                if kind=='outline':
                    d=result['document'];assert {'abstract','introduction','related_work'}<={s['kind'] for s in d['sections']};checks=[]
                    for ref in d['references']:
                        assert ref['paper_id'] in ids;identity=re.sub(r'v\d+$','',ref['arxiv_id']);e=EXPECTED[identity]
                        checks.append({'paper_id':ref['paper_id'],'title_matches':key(ref['title'])==key(e['title']),'year_matches':ref['year']==e['year'],
                            'authors_in_order_match_pdf':[key(n) for n in ref['authors']]==[key(n) for n in e['authors']],
                            'reference':ref,'canonical':e,'official_url':'https://arxiv.org/abs/'+identity,
                            'name_note':'PDF author is Edward Hu; arXiv catalog writes Edward J. Hu' if identity=='2106.09685' else None})
                    assert checks and all(x['title_matches'] and x['year_matches'] and x['authors_in_order_match_pdf'] for x in checks)
                    write(out/'reference-checks.json',checks);row.update(reference_count=len(checks),all_references_verified=True,sections=len(d['sections']))
                else:
                    formats={s['format'] for s in result['topology']['scripts']};assert formats=={'tikz','dot','mermaid','matplotlib'}
                    for s in result['topology']['scripts']:(out/('topology.'+{'tikz':'tex','dot':'dot','mermaid':'mmd','matplotlib':'py'}[s['format']])).write_text(s['script'],encoding='utf8')
                    with (out/'matplotlib-render.log').open('w',encoding='utf8') as log:
                        rendered=subprocess.run([sys.executable,'topology.py'],cwd=out,stdout=log,stderr=subprocess.STDOUT,timeout=90)
                    assert rendered.returncode==0 and (out/'topology.png').read_bytes().startswith(b'\x89PNG')
                    row.update(nodes=len(result['topology']['nodes']),edges=len(result['topology']['edges']),formats=sorted(formats),matplotlib_rendered=True,tikz_compiled=False)
            record(row)
        start=time.monotonic()
        with (BASE/'chinese-acceptance.pdf').open('rb') as f:r=c.post('/api/v2/uploads',files={'files':('authored-chinese-acceptance.pdf',f,'application/pdf')},data={'file_count':'1'})
        r.raise_for_status();upload=wait_task(c,r.json(),out/'chinese-upload.json');assert upload['status']=='completed'
        pid=upload['result']['succeeded'][0]['paper_id'];write(BASE/'chinese-paper.json',{'paper_id':pid});record({'case':'chinese_upload','status':upload['status'],'paper_id':pid,'seconds':round(time.monotonic()-start,3)})
        for scope in ['abstract','full']:
            start=time.monotonic();r=c.post(f'/api/v2/papers/{pid}/translation-tasks',json={'scope':scope,'target':'en'});r.raise_for_status();t=wait_task(c,r.json(),out/(scope+'-en-task.json'))
            row={'case':scope+'_en','task_id':t['id'],'status':t['status'],'seconds':round(time.monotonic()-start,3),'error':t.get('error')}
            if t['status']=='completed':
                value=t['result']['translation'];segments=value['segments'];assert value['metadata']['complete'] and value['metadata']['model_calls']
                for s in segments:
                    assert s['translated_text'].strip();check_numbers(s['source_text'],s['translated_text'],s['source_chunk_id'])
                    _,spans=protect(s['source_text'],formula=s['type']=='formula',numbers=False)
                    assert all(text in s['translated_text'] for text in spans.values())
                    if s['type']!='formula':assert not re.search(r'[\u3400-\u9fff]',s['translated_text'])
                target='\n'.join(s['translated_text'] for s in segments).lower()
                for term in ['encoder','decoder','attention']:assert term in target
                assert re.search(r'low[ -]rank adaptation',target)
                if scope=='full':assert 'return x + 1' in target and '$f(x) = x^2 + 1$' in target and value['markdown']
                row.update(segments=len(segments),expected_segments=value['metadata']['expected_segments'],model_calls=len(value['metadata']['model_calls']),numbers_checked=True,terms_checked=['encoder','decoder','attention','low-rank adaptation'],protected_spans_checked=True)
            record(row)
    report['passed']=all(r['status']=='completed' for r in report['cases']);write(out/'results.json',report);raise SystemExit(0 if report['passed'] else 1)
