"""Content-grounded recommendations with visible local scores and feedback evidence."""
from datetime import datetime, timezone
import copy
import hashlib
import json
import math
import re
from urllib.parse import urlparse

from fastapi import APIRouter, Query
from .errors import PipelineError
from .grounded_model import evidence_candidates
from .qa_evidence import terms
from .recommendations import recommendations
from .recommendation_feedback import rerank, FEEDBACK_FORMULA
from .reference_identity import arxiv_key, title_key
from .tracking_routes import FeedbackRequest
from .tracking_state import TrackingState, operation_lock, utc_now
from .validation import chunk_anchor
from .workspace_repository import WorkspaceRepository
from .normalize import is_references

FORMULA = 'base_score = 100*(0.50*content_jaccard + 0.25*local_pagerank + 0.15*recency + 0.10*source_github_link); missing signals contribute 0'


def content(bundle):
    abstract = [c for c in bundle['chunks'] if any('abstract' in p.casefold() or '摘要' in p for p in c['section_path']) and len(c['text']) > 100][:3]
    text = (bundle['paper_meta']['title'] or '') + ' ' + (bundle['paper_meta']['abstract'] or ' '.join(c['text'] for c in abstract))
    return text, terms(text)


def code_links(bundle):
    result = []
    for chunk in bundle['chunks']:
        if is_references(chunk):
            continue
        for raw in re.findall(r'''https?://github\.com/[^\s<>\])}"'`]+''', chunk['text']):
            parsed = urlparse(raw.rstrip('.,;:。；，'))
            parts = parsed.path.strip('/').split('/')
            if len(parts) < 2 or any(not re.fullmatch(r'[A-Za-z0-9_.-]+', p) for p in parts[:2]):
                continue
            url = 'https://github.com/' + '/'.join(parts[:2])
            if all(item['url'] != url for item in result):
                result.append({'url': url, 'anchor': chunk_anchor(chunk)})
    return result[:5]


def content_reason(seed, paper, overlap, links, signals):
    name = seed['title'] or '所选论文'
    candidate = paper['title'] or '该候选论文'
    shared = '、'.join(sorted(overlap)[:8])
    parts = [f'相对《{name}》，《{candidate}》的标题与摘要' + (f'共享主题词：{shared}。' if shared else '未发现明确主题词重合。')]
    if signals.get('graph_neighbor'):
        parts.append('两篇之间存在已核验的库内引用关系，可查看引用图谱。')
    if links:
        parts.append('原文提供可定位的GitHub链接，代码项增加10分；仓库内容和可运行性需另行核验。')
    if not shared and not signals.get('graph_neighbor'):
        parts.append('主要由本地网络与年份信号进入列表，内容相关性依据较弱。')
    return ' '.join(parts)


def _base_recommendations(workspace, seed, year):
    repository = WorkspaceRepository(workspace)
    base = recommendations(repository, seed, year)
    seed_bundle = repository.paper(seed)
    seed_text, seed_terms = content(seed_bundle)
    seed_paper = seed_bundle['paper_meta']
    results = []
    for item in base:
        paper = item['paper']
        if seed_paper['arxiv_id'] and paper['arxiv_id'] and arxiv_key(seed_paper['arxiv_id']) == arxiv_key(paper['arxiv_id']):
            continue
        if seed_paper['title'] and title_key(seed_paper['title']) == title_key(paper['title']):
            continue
        bundle = repository.paper(paper['id'])
        _, other = content(bundle)
        overlap, union = seed_terms & other, seed_terms | other
        relevance = len(overlap) / len(union) if union else 0
        links = code_links(bundle)
        signals = item['signals']
        item['score'] = 100 * (.5 * relevance + .25 * (signals['pagerank_normalized'] or 0) + .15 * (signals['recency'] or 0) + .1 * bool(links))
        excerpt = evidence_candidates(bundle, seed_text[:1500], limit=1)
        item.update(content_similarity=relevance, matched_terms=sorted(overlap)[:16], code_links=links,
                    excerpt={'quote': excerpt[0]['quote'], 'anchor': excerpt[0]['anchor']} if excerpt else None,
                    relationship_reason=content_reason(seed_paper, paper, overlap, links, signals),
                    seed_paper={'id':seed, 'title':seed_paper['title']},
                    code_priority_bonus=10 if links else 0)
        # The v2 score uses source chunks for code detection, so legacy metadata-only
        # missing flags must not contradict the actual code evidence shown here.
        item['signals']['github_link'] = 1 if links else None
        item['missing_signals'] = [s for s in item['missing_signals'] if s != 'github_link'] + ([] if links else ['github_link'])
        item['scoring_version'] = 'workspace-content-v1'
        results.append(item)
    results.sort(key=lambda item: (-item['score'], item['paper']['id']))
    return results


def recommendation_signature(workspace):
    sources = [(str(p.relative_to(workspace.root)), p.stat().st_mtime_ns, p.stat().st_size)
               for p in sorted((workspace.root/'papers').glob('*/*.json'))]
    with workspace.lock, workspace.connect() as db:
        rows = db.execute("SELECT kind,id,value FROM records WHERE kind IN ('paper','enrichment','classification','layout_page') ORDER BY kind,id").fetchall()
    return hashlib.sha256(json.dumps([sources,rows],ensure_ascii=False).encode()).hexdigest()


def workbench_recommendations(workspace, seed, year, profile='local', votes=None, diagnostics=None):
    # Cache only the grounded base scores, never a user's votes or final ranking.
    # Metadata, versions, classification, source bundles and year invalidate it.
    key=(seed,year,recommendation_signature(workspace))
    cached=getattr(workspace,'_recommendation_base_cache',{})
    hit=key in cached
    if hit:
        results=copy.deepcopy(cached[key])
    else:
        results=_base_recommendations(workspace,seed,year)
        if key[2]==recommendation_signature(workspace):
            workspace._recommendation_base_cache={key:copy.deepcopy(results)}
    if diagnostics is not None:
        diagnostics.update(base_cache_hit=hit,library_signature=key[2],cached_profiles=False)
    repository=WorkspaceRepository(workspace)
    values = TrackingState(workspace.root).votes(profile) if votes is None else votes
    return rerank(repository, results, values)


def recommendation_routes(workspace):
    router = APIRouter(prefix='/api/v2')

    @router.get('/recommendations')
    def recommend(paper_id: str, profile_id: str = Query('local', pattern=r'^[A-Za-z0-9._-]{1,64}$')):
        year = datetime.now(timezone.utc).year
        diagnostics={}
        items=workbench_recommendations(workspace, paper_id, year, profile_id,diagnostics=diagnostics)
        return {'items': items, 'diagnostics':diagnostics,
                'votes': TrackingState(workspace.root).votes(profile_id),
                'scoring': FORMULA, 'feedback_formula': FEEDBACK_FORMULA, 'computed_at': utc_now(), 'as_of_year': year}

    @router.post('/recommendations/feedback')
    def feedback(body: FeedbackRequest):
        if body.paper_id == body.seed_paper_id:
            raise PipelineError('VALIDATION_ERROR', '请对推荐候选论文进行反馈。')
        workspace.metadata(body.paper_id); workspace.metadata(body.seed_paper_id)
        state = TrackingState(workspace.root)
        year = body.as_of_year or datetime.now(timezone.utc).year
        with operation_lock(workspace.root, 'feedback', timeout=30):
            votes = [v for v in state.votes(body.profile_id) if v['paper_id'] != body.paper_id]
            before = workbench_recommendations(workspace, body.seed_paper_id, year, body.profile_id)
            value = 1 if body.vote == 'like' else -1
            votes.append({'paper_id': body.paper_id, 'vote': value, 'updated_at': utc_now()})
            after = workbench_recommendations(workspace, body.seed_paper_id, year, body.profile_id, votes=votes)
            ranking = lambda items: [{'paper_id': item['paper']['id'], 'rank': index, 'score': item['score']} for index, item in enumerate(items, 1)]
            event = {'profile_id': body.profile_id, 'seed_paper_id': body.seed_paper_id, 'paper_id': body.paper_id,
                     'vote': value, 'at': utc_now(), 'before': ranking(before), 'after': ranking(after), 'formula': FORMULA + '; ' + FEEDBACK_FORMULA}
            return {'event_id': state.feedback(body.profile_id, body.paper_id, value, event), **event}
    return router
