"""Publish genuine outputs and compact provenance, never PDFs, keys or full parsed texts."""
import copy
import json
import shutil
from datetime import datetime
from pathlib import Path
from common import ROOT,BASE,write,digest

PUBLIC=ROOT/'test-records/item04-20261028'
def read(name):return json.loads((BASE/name).read_text(encoding='utf-8'))
def paper(value):
    if not value:return value
    result={k:v for k,v in value.items() if k!='abstract'}
    abstract=value.get('abstract') or ''
    import hashlib
    result.update(abstract_present=bool(abstract),abstract_characters=len(abstract),abstract_sha256=hashlib.sha256(abstract.encode()).hexdigest())
    return result
def task(value):
    result=copy.deepcopy(value)
    for item in (result.get('result') or {}).get('items',[]):
        for key in ['metadata','paper']:
            if item.get(key):item[key]=paper(item[key])
    return result
def ranking(value):
    return {'computed_at':value.get('computed_at'),'diagnostics':value.get('diagnostics'),'votes':value.get('votes'),
        'items':[{'rank':n,'paper':paper(row['paper']),**{k:row[k] for k in ['score','base_score','feedback_adjustment','content_similarity','matched_terms','code_links','relationship_reason','code_priority_bonus'] if k in row}}
                 for n,row in enumerate(value['items'],1)]}
def elapsed(value):return round((datetime.fromisoformat(value['finished_at'])-datetime.fromisoformat(value['started_at'])).total_seconds(),6)

if __name__=='__main__':
    PUBLIC.mkdir(exist_ok=False,parents=True)
    copied=[]
    for name in ['baseline-fast-access.log','baseline-fast-access.xml','related-first.log','related-first.xml',
       'related-second.log','related-second.xml','related-final.log','related-final.xml','final-fast.log','final-fast.xml','release-fast.log','release-fast.xml',
       'frontend-local-build.log','frontend-final-build.log','frontend-mobile-build.log','frontend-runtime-final.log','frontend-runtime-mobile.log',
       'backend-runtime-final.log','title-before.log','seed-upload.log','batch-all.log','retry-verified.log',
       'feedback-final.log','failure-before.log','failure-after.log','failure-release.log','scheduled-cycle.log',
       'polling-followup.log','recommendation-performance.log','browser-final.log','browser-verified.log','browser-secondary.log','browser-mobile-verified.log','runtime-final.log']:
        assert (BASE/name).is_file(),name
        shutil.copyfile(BASE/name,PUBLIC/name);copied.append(name)
    for name in ['seed-upload.json','reference-evaluation.json','runtime-final.json','github-check.json','github-html-check.json',
          'failure-before/result.json','failure-after/result.json','failure-release/result.json','recommendation-performance/result.json',
          'polling-followup/result.json','browser-final/result.json','browser-verified/result.json','browser-secondary/result.json','browser-mobile-verified/result.json',
          'browser-mobile-verified/weekly-schedule.json','mobile-overflow-before.json']:
        target=PUBLIC/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(BASE/name,target);copied.append(name)
    for folder,shots in {
        'browser-verified':['content-context.png','bert-like.png','bert-dislike.png','bert-refresh.png','batch-final.png'],
        'browser-mobile-verified':['title-duplicate-ui.png','discovery-1440.png','discovery-390.png','code-anchor-page8.png','failure-release-ui.png'],
        'browser-final':['failure.png'],'browser-secondary':['failure.png'],
        '':['failure-before-ui.png','failure-after-ui.png','schedule-current-ui.png']}.items():
        for name in shots:
            source=BASE/folder/name;target=PUBLIC/'screenshots'/((folder+'-' if folder else '')+name)
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    titles=[]
    for n in [1,2]:
        value=read(f'title-before/{n}-result.json');v=value['reading'];titles.append({'requested_title':value['title'],'elapsed_seconds':value['elapsed_seconds'],
            'paper':paper(v['paper']),'total_chunks':v['total_chunks'],'task':task(value['task'])})
    metadata=read('metadata-final/result.json');metadata['result']['paper']=paper(metadata['result']['paper']);metadata['result']['metadata']=paper(metadata['result']['metadata'])
    write(PUBLIC/'title-downloads.json',titles);write(PUBLIC/'metadata-final.json',metadata)
    enrichment=read('bert-operational-enrichment.json');enrichment['view']['paper']=paper(enrichment['view']['paper']);enrichment['view']['original']=paper(enrichment['view']['original'])
    write(PUBLIC/'bert-operational-enrichment.json',enrichment)
    for source,target in [('batch-all/task.json','batch-before.json'),('retry-verified/task.json','retry-after.json'),('browser-verified/batch-current.json','batch-one-click-final.json')]:
        write(PUBLIC/target,task(read(source)))
    for source,target in [('recommendations-before.json','ranking-before.json'),('browser-verified/recommendations-before.json','ranking-browser-before.json')]:
        write(PUBLIC/target,ranking(read(source)))
    for vote in ['like','dislike']:write(PUBLIC/f'feedback-browser-{vote}.json',read(f'browser-verified/feedback-{vote}.json'))
    proof=read('feedback-final/result.json');reproduction={k:proof[k] for k in ['source','source_hashes','seed','target']};reproduction['interfaces']={}
    for v,row in proof['interfaces'].items():
        reproduction['interfaces'][v]={'ranks':row['ranks'],'before':ranking(row['before']),'after_like':ranking(row['after_like']),'after_dislike':ranking(row['after_dislike']),
            'like_before_after':{k:row['like_event'][k] for k in ['before','after']},'dislike_before_after':{k:row['dislike_event'][k] for k in ['before','after']}}
    reproduction['votes_after_restart']=proof['after_restart']['votes'];write(PUBLIC/'feedback-reproduction.json',reproduction)
    for source,target in [('scheduled-cycle/status.json','scheduled-cycle.json'),('polling-followup/run.json','polling-followup.json')]:
        value=read(source)
        run=value.get('latest_run',value)
        for c in run['candidates']:
            c['metadata']=paper(c['metadata'])
            if c.get('import'):
                c['import']['metadata']=paper(c['import'].get('metadata'));c['import']['paper']=paper(c['import'].get('paper'))
        write(PUBLIC/target,value)
    plan=read('reference-plan-after-local.json')
    for row in plan:
        row['content_contexts']=[{**c,'quote':c['quote'][:160]} for c in row['content_contexts'][:2]]
    write(PUBLIC/'reference-context-plan.json',plan)
    # Retain the pre-scoring labels; correct the discovered review omission separately.
    evaluation=read('reference-evaluation.json');corrected_positive=set(evaluation['rubric']['positive_numbers'])|{36}
    review={'correction':'原冻结草稿漏将[36]列入直接训练方法；原文5.4明确采用label smoothing。保留草稿分数，不把事后修订结果冒充独立准确率。',
        'positive_numbers_after_review':sorted(corrected_positive),'before':{},'after':{},
        'basis':{'anchor':next(r for r in plan if r['reference']['number']==36)['content_contexts'][0]['anchor'],
                 'assessment':'Section 5.4 actual parsed citation [36]. Single reviewer, no external gold labels.'}}
    for key,rows in [('before',evaluation['before_frequency']['top_10']),('after',evaluation['after_context']['top_10'])]:
        tp=len(set(rows)&corrected_positive);fp=10-tp;fn=len(corrected_positive-set(rows));tn=40-tp-fp-fn
        review[key]={'top10_precision_against_revised_draft':tp/10,'recall':tp/len(corrected_positive),'binary_accuracy_at_top10_cutoff':(tp+tn)/40,'tp':tp,'fp':fp,'fn':fn,'tn':tn}
    write(PUBLIC/'reference-label-review.json',review)
    before=read('batch-all/task.json');retry=read('retry-verified/task.json');final=read('browser-verified/batch-current.json')
    remaining=final['result']['failed'];plan_before=read('reference-plan-before.json')
    missing=[{**next(r['reference'] for r in plan_before if r['reference']['title']==f['filename']),'error':{'error_code':f['error_code'],'message':f['message']}} for f in remaining]
    write(PUBLIC/'remaining-references.json',missing)
    summary={'title_downloads':[{'title':v['requested_title'],'seconds':v['elapsed_seconds'],'pages':v['paper']['page_count'],'chunks':v['total_chunks']} for v in titles],
        'batch_before':{'seconds':elapsed(before),**{k:v for k,v in before['result'].items() if k.endswith('count')}},
        'retry':{'seconds':elapsed(retry),**{k:v for k,v in retry['result'].items() if k.endswith('count')}},
        'batch_final':{'seconds':elapsed(final),**{k:v for k,v in final['result'].items() if k.endswith('count')}},
        'missing_numbers':[m['number'] for m in missing],
        'verdict':'未通过完整下载验收：32/40取得，8条未取得唯一arXiv全文；已修复的网页与业务链路通过实测。'}
    write(PUBLIC/'summary.json',summary)
    manifest=[]
    for path in sorted(PUBLIC.rglob('*')):
        if path.is_file():manifest.append({'path':str(path.relative_to(PUBLIC)).replace('\\','/'),'bytes':path.stat().st_size,'sha256':digest(path)})
    write(PUBLIC/'manifest.json',{'files':manifest,'raw_command_logs':copied,'private_original_root':'data/item04-20261028','full_pdfs_and_traces_in_git':False})
    print(json.dumps({'public_files':len(manifest),'summary':summary},ensure_ascii=False))
