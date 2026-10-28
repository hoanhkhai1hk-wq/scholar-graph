"""Content-grounded recommendations with visible local scores and feedback evidence."""
from datetime import datetime, timezone
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

FORMULA = 'base_score = 100*(0.50*content_jaccard + 0.25*local_pagerank + 0.15*recency + 0.10*source_github_link); missing signals contribute 0'


def content(bundle):
    abstract = [c for c in bundle['chunks'] if any('abstract' in p.casefold() or '摘要' in p for p in c['section_path']) and len(c['text']) > 100][:3]
    text = (bundle['paper_meta']['title'] or '') + ' ' + (bundle['paper_meta']['abstract'] or ' '.join(c['text'] for c in abstract))
    return text, terms(text)


def code_links(bundle):
    result = []
    for chunk in bundle['chunks']:
        for raw in re.findall(r'https?://github\.com/[^\s<>\])}]+', chunk['text']):
            parsed = urlparse(raw.rstrip('.,;:。；，'))
            parts = parsed.path.strip('/').split('/')
            if len(parts) < 2 or any(not re.fullmatch(r'[A-Za-z0-9_.-]+', p) for p in parts[:2]):
                continue
            url = 'https://github.com/' + '/'.join(parts[:2])
            if all(item['url'] != url for item in result):
                result.append({'url': url, 'anchor': chunk_anchor(chunk)})
    return result[:5]


def workbench_recommendations(workspace, seed, year, profile='local', votes=None):
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
                    excerpt={'quote': excerpt[0]['quote'], 'anchor': excerpt[0]['anchor']} if excerpt else None)
        item['scoring_version'] = 'workspace-content-v1'
        results.append(item)
    results.sort(key=lambda item: (-item['score'], item['paper']['id']))
    values = TrackingState(workspace.root).votes(profile) if votes is None else votes
    return rerank(repository, results, values)


def recommendation_routes(workspace):
    router = APIRouter(prefix='/api/v2')

    @router.get('/recommendations')
    def recommend(paper_id: str, profile_id: str = Query('local', pattern=r'^[A-Za-z0-9._-]{1,64}$')):
        year = datetime.now(timezone.utc).year
        return {'items': workbench_recommendations(workspace, paper_id, year, profile_id),
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
