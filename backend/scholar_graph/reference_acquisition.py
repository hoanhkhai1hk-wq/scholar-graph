"""V2 only: resolve an abbreviated citation title with strict author/year guards."""
from .arxiv_fetch import normalized_title
from .errors import PipelineError
from .reference_identity import surnames


def fetch_reference(fetcher, reference):
    result = fetcher.fetch(reference=reference)
    if result['succeeded'] or result['error']['error_code'] != 'PAPER_NOT_FOUND':
        return result
    title = reference.get('title')
    people = surnames(reference.get('authors') or [])
    # Identifiers remain authoritative, and ambiguous/anonymous citations stay unresolved.
    if reference.get('arxiv_id') or reference.get('doi') or not title or not people or not reference.get('year'):
        return result
    query = 'ti:"' + title.replace('"', '') + '"'
    try:
        candidates = fetcher.client.search(query, limit=5)
    except PipelineError:
        return result
    key = normalized_title(title)
    matches = [paper for paper in candidates if
        len(key) >= 20 and normalized_title(paper['title']).startswith(key)
        and paper['year'] == reference['year'] and surnames(paper['authors']) == people]
    if len(matches) != 1:
        return result
    resolved = fetcher.fetch_metadata(matches[0])
    resolved['reference_resolution'] = {'method':'unique_title_prefix_all_author_surnames_year',
        'source_title':title,'resolved_title':matches[0]['title'],'source_year':reference['year'],
        'matched_surnames':sorted(people),'candidate_count':len(candidates),
        'notice':'原参考文献标题为缩写；已以完整作者姓氏集合、年份和唯一标题前缀核对。原引用记录未改写。'}
    return resolved
