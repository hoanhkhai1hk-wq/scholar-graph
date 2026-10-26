"""Fail-open default enrichment with immutable MinerU anchors and explicit provenance."""
import copy
import os
import time

from .errors import PipelineError
from .grobid import GrobidClient
from .normalize import citation_links
from .reference_identity import title_key,arxiv_key,surnames,bibliography_sources

HEADER_FIELDS=('title','authors','institutions','abstract','year','doi')


def present(value):
    return value is not None and value!=[] and value!=''


def reference_match(local,remote,raw):
    for field,key in [('doi',str.casefold),('arxiv_id',arxiv_key)]:
        if local[field] and remote[field] and key(local[field])!=key(remote[field]):
            return None
    for field,key in [('doi',str.casefold),('arxiv_id',arxiv_key)]:
        if local[field] and remote[field] and key(local[field])==key(remote[field]):
            return field
    title=title_key(remote['title'])
    if len(title)>=8 and (title==title_key(local['title']) or title in title_key(raw)):
        return 'title'
    if title and (local['title'] or raw):
        return None  # A conflicting written title cannot be overruled by a common surname/year.
    if (local['year'] and local['year']==remote['year'] and surnames(local['authors'])
            and surnames(local['authors']) & surnames(remote['authors'])):
        return 'author-year'
    return None


def merge(local,remote,gate,authority=()):
    gate.bundle(remote)
    if remote['chunks']!=local['chunks']:
        raise PipelineError('VALIDATION_ERROR','GROBID 不得替换 MinerU Chunk 与物理页锚点。')
    output=copy.deepcopy(local)
    fields=[]
    for field in HEADER_FIELDS:
        # Explicit local identities/dates, or verified arXiv catalog fields, win.
        if (field in authority or field in ('doi','year')) and present(local['paper_meta'][field]):
            continue
        if present(remote['paper_meta'][field]):
            output['paper_meta'][field]=remote['paper_meta'][field]
            if output['paper_meta'][field]!=local['paper_meta'][field]:fields.append(field)
    sources={r['number']:r['raw'] for r in bibliography_sources(local['chunks'])}
    by_number={r['number']:r for r in remote['reference_entries']}
    matches=[]
    for reference in output['reference_entries']:
        other=by_number.get(reference['number'])
        if other is None:continue
        method=reference_match(reference,other,sources.get(reference['number'],''))
        if method is None:continue
        changed=[]
        for field in ('authors','year','title','venue','doi','arxiv_id'):
            if present(other[field]) and reference[field]!=other[field]:
                reference[field]=other[field];changed.append(field)
        matches.append({'ref_id':reference['ref_id'],'method':method,'fields':changed})
    # Keep original occurrence anchors; add only links reconstructed from real chunks.
    links=output['citation_links']+citation_links(output['chunks'],output['reference_entries'])
    output['citation_links']=list({tuple(link[k] for k in ('paper_id','citation_number','page_number','chunk_id','ref_id')):link for link in links}.values())
    gate.bundle(output)
    return output,{'paper_fields':fields,'reference_matches':matches,
        'references_enriched':sum(bool(m['fields']) for m in matches),
        'unmatched_grobid_references':len(remote['reference_entries'])-len(matches)}


class DefaultGrobid:
    def apply(self,bundle,raw,gate,authority=()):
        metadata={'method':'mineru','grobid_attempted':False,'grobid_elapsed_seconds':0.0,
            'fallback_reason':None,'grobid_error':None,'paper_fields':[],
            'reference_matches':[],'references_enriched':0}
        started=time.perf_counter()
        try:
            flag=os.environ.get('SCHOLAR_GRAPH_GROBID_ENABLED','true').casefold()
            if flag in ('false','0'):
                metadata['disabled']=True
                return bundle,metadata
            if flag not in ('true','1'):raise ValueError('invalid flag')
            timeout=float(os.environ.get('SCHOLAR_GRAPH_GROBID_TIMEOUT','60'))
            if not 0<timeout<=120:raise ValueError('invalid timeout')
            client=GrobidClient(os.environ.get('GROBID_URL','http://127.0.0.1:8070'),timeout=timeout)
            metadata['grobid_attempted']=True
            candidate=client.enrich(copy.deepcopy(bundle),raw)
            output,details=merge(bundle,candidate,gate,authority)
            if output==bundle:
                raise PipelineError('UPSTREAM_ERROR','GROBID 未提供可合并的增强字段，保留 MinerU 原结果。')
            metadata.update(details,method='mineru+grobid')
            return output,metadata
        except Exception as error:
            if not isinstance(error,PipelineError):
                error=PipelineError('UPSTREAM_ERROR','GROBID 配置或增强结果无效，保留 MinerU 原结果。')
            metadata.update(method='mineru-fallback',fallback_reason=error.message,grobid_error=error.envelope())
            return bundle,metadata
        finally:
            metadata['grobid_elapsed_seconds']=round(time.perf_counter()-started,6)
