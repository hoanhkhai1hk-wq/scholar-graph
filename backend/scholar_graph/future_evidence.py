"""Source-balanced future evidence and deterministic date/quotation publication checks."""
import re
from .errors import PipelineError
from .grounded_model import evidence_candidates,evidence_from_chunks

def future_sources(bundles):
    if not bundles:return []
    limit=max(1,min(12,60//len(bundles)))
    rows=[]
    for bundle in bundles:
        explicit=[c for c in bundle['chunks'] if c['type']=='text' and len(c['text'])>=40 and
            re.search(r'future work|future research|we plan|we intend|further research|remains? (?:an? |to be)|未来工作|未来研究',c['text'],re.I)]
        selected=evidence_from_chunks(bundle,explicit,'future work',limit=limit) if explicit else evidence_candidates(bundle,'future work directions limitations conclusion',limit=limit)
        rows.extend(selected)
    return [{**r,'evidence_id':f'e{i}'} for i,r in enumerate(rows,1)]

def local_candidates(bundles,source_id,source_year,queries):
    result=[]
    for bundle in bundles:
        meta=bundle['paper_meta']
        if meta['id']==source_id or source_year is None or meta['year'] is None or meta['year']<=source_year:continue
        # A later paper's bibliography is not evidence that its authors attempted
        # the cited technique, and must not inherit the host paper's year.
        body={**bundle,'chunks':[c for c in bundle['chunks'] if not any(
            re.match(r'^(?:references|bibliography|参考文献)\b',s.strip(),re.I) for s in c['section_path'])]}
        rows=[]
        for query in queries:rows.extend(evidence_candidates(body,query,limit=2))
        rows=list({r['anchor']['chunk_id']:r for r in rows}.values())[:4]
        if rows:result.append({**meta,'candidate_origin':'selected_library','source_passages':[{'quote':r['quote'],'anchor':r['anchor']} for r in rows]})
    return result

def checked_comparison(value,papers,source_year,original_topic):
    required={'decision','reason','matches'}
    if (not isinstance(value,dict) or not required<=set(value)<=required|{'remaining_topic','attempted'} or
        value['decision'] not in ('include','exclude','uncertain') or not isinstance(value['reason'],str) or
        not isinstance(value['matches'],list)):
        raise PipelineError('VALIDATION_ERROR','更新研究对照格式不正确。')
    lookup={p['id']:p for p in papers};matches=[]
    for match in value['matches']:
        if not isinstance(match,dict) or set(match)!={'candidate_id','quote'}:raise PipelineError('VALIDATION_ERROR','更新研究引文格式不正确。')
        candidate=lookup.get(match['candidate_id']);quote=match['quote']
        if not candidate or not isinstance(quote,str) or not quote or len(quote)>3000:raise PipelineError('VALIDATION_ERROR','更新研究的引文无法核对。')
        passages=[p for p in candidate.get('source_passages',[]) if quote in p['quote']]
        if quote not in (candidate.get('abstract') or '') and not passages:raise PipelineError('VALIDATION_ERROR','更新研究的引文无法核对。')
        matches.append({**match,'year':candidate['year'],**({'anchor':passages[0]['anchor']} if passages else {})})
    result={k:value[k] for k in required};result['matches']=matches
    dated=bool(matches) and source_year is not None and all(lookup[m['candidate_id']]['year'] is not None and lookup[m['candidate_id']]['year']>source_year for m in matches)
    if 'attempted' in value and value['attempted'] is not None and type(value['attempted']) is not bool:raise PipelineError('VALIDATION_ERROR','是否已有尝试的判定格式不正确。')
    result['attempted']=value.get('attempted')
    if value.get('attempted') is True:
        result.update(decision='exclude' if dated else 'uncertain')
        if value.get('remaining_topic'):result['remaining_candidate']={'topic':value['remaining_topic'],'decision':'uncertain','notice':'原方向已被尝试；此更窄设想尚未完成独立查新，不作为已证实的新方向。'}
    if value['decision']=='exclude' and not dated:
        result.update(decision='uncertain',reason='发表时间或对应尝试的证据不足，不能据此排除。')
    if result['decision']=='include':
        remaining=value.get('remaining_topic')
        contradiction=re.search(r'不宜.{0,12}(?:未探索|推荐)|已有.{0,30}(?:尝试|应用)|已经.{0,20}(?:尝试|应用)',value['reason'])
        gap=any(re.search(r'remain|unresolved|open problem|future|still|challenge|not yet|尚未|仍然|未来',m['quote'],re.I) for m in matches)
        if not dated or not isinstance(remaining,str) or not 5<=len(remaining)<=200 or remaining==original_topic or not gap or contradiction:
            result.update(decision='uncertain',reason='未形成有较新原文支持的具体剩余缺口，或结论与理由矛盾；暂不作为值得探索方向推荐。'+value['reason'])
        else:result['remaining_topic']=remaining
    result['date_check']={'source_year':source_year,'matched_years':[m['year'] for m in matches],'strictly_later':dated}
    return result
