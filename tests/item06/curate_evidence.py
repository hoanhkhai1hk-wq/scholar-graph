"""Check actual source anchors and produce bounded public evidence without original PDFs."""
import json,re,shutil,hashlib,csv,sys
from decimal import Decimal,localcontext
from common import ROOT,BASE,write,digest
from live_models import EXPECTED,key
sys.path.insert(0,str(ROOT/'backend'))
from scholar_graph.translation import check_numbers,protect
from scholar_graph.topology import parse_script
OUT=ROOT/'test-records/item06-20261029'
def read(name):return json.loads((BASE/name).read_text(encoding='utf8'))
def qhash(s):return hashlib.sha256(s.encode()).hexdigest()
if __name__=='__main__':
    OUT.mkdir(exist_ok=True);chunks={}
    for p in (BASE/'records/papers').glob('*/chunks.json'):
        for c in json.loads(p.read_text(encoding='utf8')):chunks[c['chunk_id']]=c
    def anchor(a,quote=None):
        c=chunks[a['chunk_id']];assert a['paper_id']==c['paper_id'] and a['page_number']==c['page_number'] and a['section']==c['section_path']
        if quote:assert ' '.join(quote.split()) in ' '.join(c['text'].split())
    bibliography=[];paragraphs=[]
    for run in ['live-repaired','browser-final']:
        task=read(run+'/outline-task.json');assert task['status']=='completed';doc=task['result']['document'];selected={r['paper_id'] for r in read('selected-papers.json')}
        for ref in doc['references']:
            assert ref['paper_id'] in selected;identity=re.sub(r'v\d+$','',ref['arxiv_id']);expected=EXPECTED[identity]
            assert key(ref['title'])==key(expected['title']) and ref['year']==expected['year'] and list(map(key,ref['authors']))==list(map(key,expected['authors']))
            bibliography.append({'run':run,'task_id':task['id'],'reference':ref,'official_url':'https://arxiv.org/abs/'+identity,'canonical_pdf_metadata':expected,
                'author_note':'Original PDF signs Edward Hu; arXiv catalog writes Edward J. Hu.' if identity=='2106.09685' else None,'passed':True})
        for section in doc['sections']:
            for p in section['paragraphs']:
                citations=[]
                for c in p['citations']:anchor(c['anchor'],c['quote']);citations.append({'anchor':c['anchor'],'quote_sha256':qhash(c['quote'])})
                paragraphs.append({'run':run,'section':section['kind'],'type':p['type'],'text':p['text'],'citations':citations})
    write(OUT/'references-audit.json',bibliography);write(OUT/'outline-paragraph-audit.json',paragraphs)
    translation=[]
    for scope in ['abstract','full']:
        task=read('live-repaired/'+scope+'-en-task.json');value=task['result']['translation'];assert task['status']=='completed' and value['metadata']['complete']
        checked=[]
        for s in value['segments']:
            c=chunks[s['source_chunk_id']];assert c['text']==s['source_text'] and c['page_number']==s['page_number'];check_numbers(s['source_text'],s['translated_text'],s['source_chunk_id'])
            _,spans=protect(s['source_text'],formula=s['type']=='formula',numbers=False);assert all(p in s['translated_text'] for p in spans.values())
            checked.append({'chunk_id':s['source_chunk_id'],'page':s['page_number'],'source_sha256':qhash(s['source_text']),'translation_sha256':qhash(s['translated_text']),'number_check':True,'protected_characters_retained':True})
        translation.append({'scope':scope,'task_id':task['id'],'segments':len(checked),'expected':value['metadata']['expected_segments'],'metadata':value['metadata'],'checks':checked})
    write(OUT/'translation-audit.json',translation)
    full=read('live-repaired/full-en-task.json')['result']['translation']['segments']
    close=next(i for i,s in enumerate(full) if s['source_text'].strip()=='```')
    returned=next(i for i,s in enumerate(full) if s['source_text'].strip()=='return x + 1')
    assert close<returned
    write(OUT/'code-order-issue.json',{'status':'not_passed','scope':'extra source-PDF cross-chunk code-order check; distinct from requested terminology/numeric checks',
        'closing_fence_segment_index':close,'return_segment_index':returned,'original_pdf_visual_return_precedes_closing_fence':True,
        'source_pdf_page_image_sha256':digest(BASE/'chinese-source-page-2.png'),
        'affected_chunks':[{'chunk_id':full[i]['source_chunk_id'],'text':full[i]['source_text'],'source_bbox':chunks[full[i]['source_chunk_id']]['bbox']} for i in [close,returned]],
        'next_action':'Repair PDF code-region reading order in parsing acceptance, then rerun translation and Markdown checks.'})
    raw=(BASE/'matrix-timings.csv').read_bytes();rows=list(csv.DictReader(raw.decode().splitlines()));chart_summary=[]
    for kind in ['table','line','bar','radar3d']:
        v=read('browser-final/'+kind+'-response.json');assert len(v['numeric_checks'])==15
        for check in v['numeric_checks']:
            a=check['csv_anchor'];assert Decimal(str(check['value']))==Decimal(rows[a['row_number']-2][a['column_name']])
        for caption in v['captions']:
            f=caption['numeric_facts'];name=caption['series_name'];assert f['first']['text']==rows[0][name] and f['last']['text']==rows[-1][name]
            with localcontext() as c:c.prec=1000;assert Decimal(f['delta']['value'])==Decimal(rows[-1][name])-Decimal(rows[0][name])
        value={k:v[k] for k in ['kind','csv_ref','data_table','numeric_checks','captions','caption_method','radar_note']};write(OUT/'charts'/(kind+'.json'),value)
        chart_summary.append({'kind':kind,'rows':len(v['data_table']['rows']),'source_cell_checks':len(v['numeric_checks']),'captions':len(v['captions']),'traceable_endpoint_and_difference_facts':sum(len(c['numeric_facts']) for c in v['captions'])})
    write(OUT/'charts/summary.json',chart_summary)
    graph=read('final-visual/topology-response.json');graphs=[parse_script(s['script'],s['format']) for s in graph['scripts']];assert all(g==graphs[0] for g in graphs)
    for kind in ['nodes','edges']:
        for item in graph[kind]:
            for a in item['anchors']:anchor(a)
    write(OUT/'topology-audit.json',{'nodes':len(graph['nodes']),'edges':len(graph['edges']),'four_formats_same_graph':True,'anchors_checked':True,'native_source_task_id':read('browser-final/topology-task.json')['id'],'final_render_uses_same_model_logic':read('final-visual/same-model-logic.json'),'renderers':read('final-visual/rendered/result.json')})
    for name in ['baseline-fast.log','baseline-fast.xml','baseline.log','baseline-charts.log','experiment.log','experiment-fixed.log','matrix-experiment.json','chinese-fixture.json','repair-tests.log','repair-escalated.log','repair-escalated.xml','stalled-process.json','frontend-readable-build.log','index-build.log','related-release.log','related-release.xml','fast-release.log','fast-release.xml','browser-before.log','browser-before2.log','browser-before3.log','browser-final.log','render-native.log','render-native-external.log','render-fixed-external.log','final-visual-external.log','runtime-audit.log','runtime-audit-final.log','runtime-audit-delivery.log','runtime-audit.json','release-runtime-final.log','release-commands.json','live-repaired.log']:
        if (BASE/name).exists():shutil.copyfile(BASE/name,OUT/name)
    shutil.copyfile(BASE/'matrix-timings.csv',OUT/'matrix-timings.csv')
    for name in ['live-repaired/results.json','live-repaired/reference-checks.json','browser-before3/result.json','browser-final/result.json','browser-final/script-equivalence.json']:
        write(OUT/name,read(name))
    for path in (BASE/'browser-final').glob('*.png'):
        target=OUT/'browser-final'/path.name;target.parent.mkdir(exist_ok=True);shutil.copyfile(path,target)
    for name in ['browser-before3/table-missing.png','chinese-source-page-1.png','chinese-source-page-2.png','final-visual/topology.png','final-visual/topology.py','final-visual/topology.dot','final-visual/topology.mmd','final-visual/topology.tex','final-visual/rendered/dot.png','final-visual/rendered/dot.svg','final-visual/rendered/mermaid.png','final-visual/rendered/mermaid.svg']:
        target=OUT/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(BASE/name,target)
    write(OUT/'private-evidence-sha256.json',{name:digest(BASE/name) for name in ['baseline/outline-task.json','live-repaired/outline-task.json','live-repaired/topology-task.json','live-repaired/abstract-en-task.json','live-repaired/full-en-task.json','browser-final/outline-task.json','browser-final/topology-task.json','browser-final/trace.zip','chinese-acceptance.pdf','final-visual/topology-response.json']})
    print(json.dumps({'reference_rows_checked':len(bibliography),'paragraphs_checked':len(paragraphs),'translated_scopes':len(translation),'charts':len(chart_summary),'graph_nodes':len(graph['nodes']),'graph_edges':len(graph['edges'])}))
