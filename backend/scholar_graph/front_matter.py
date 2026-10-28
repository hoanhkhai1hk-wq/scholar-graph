"""Conservative missing-field recovery from actual first-page text and coordinates."""
import re
from .author_metadata import source_author_profiles, ORG, EMAIL


def local_front_matter(bundle):
    meta = dict(bundle['paper_meta']); patch, proofs = {}, {}
    chunks = sorted([c for c in bundle['chunks'] if c['page_number'] == 1 and c['bbox']], key=lambda c: (round(c['bbox'][1]/.012), c['bbox'][0]))
    title = None
    if not meta['title']:
        candidates = [c for c in chunks if .03 <= c['bbox'][1] <= .25 and .15 < (c['bbox'][0]+c['bbox'][2])/2 < .85
                      and .25 <= c['bbox'][2]-c['bbox'][0] and 10 <= len(c['text']) <= 180
                      and not re.search(r'@|arxiv|https?://|copyright|proceedings|conference|draft|preprint', c['text'], re.I)
                      and not re.match(r'^\d', c['text'])]
        if candidates:
            title = candidates[0]; patch['title'] = meta['title'] = title['text']; proofs['title'] = [title['chunk_id']]
    abstract = next((c for c in chunks if c['text'].strip().casefold() in ('abstract', '摘要')), None)
    if not meta['abstract'] and abstract:
        lines = []
        bottom = min((c['bbox'][1] for c in chunks if c['bbox'][1] > abstract['bbox'][3] and re.match(r'^\d+(?:\.\d+)*\s+[A-Z]', c['text'])), default=.88)
        for chunk in chunks:
            if abstract['bbox'][3] <= chunk['bbox'][1] < bottom and len(chunk['text']) >= 15 and not chunk['text'].startswith(('*', '†', '‡', '∗')):
                lines.append(chunk)
        text = ' '.join(c['text'] for c in lines)
        if len(text) >= 100:
            patch['abstract'] = text; proofs['abstract'] = [c['chunk_id'] for c in lines]
    profiles = source_author_profiles({**bundle, 'paper_meta': meta}, meta['authors'])
    if not profiles and title and not abstract:
        # A single centered name immediately below a book cover title is distinct
        # from a copyright holder or a date lower on the page.
        people = [c for c in chunks if title['bbox'][3] < c['bbox'][1] < title['bbox'][3]+.12
                  and not ORG.search(c['text']) and not EMAIL.search(c['text'])
                  and re.fullmatch(r"[A-Z][A-Za-z.'’\-]*(?:\s+[A-Z][A-Za-z.'’\-]*){1,4}", c['text'].strip())]
        if len(people) == 1:
            profiles = source_author_profiles(bundle, [people[0]['text']])
    if not meta['authors'] and profiles and all(p['anchors'] for p in profiles):
        patch['authors'] = [p['name'] for p in profiles]
        patch['institutions'] = list(dict.fromkeys(org for p in profiles for org in p['institutions']))
        proofs['authors'] = [a['chunk_id'] for p in profiles for a in p['anchors']]
    return patch, profiles, proofs


def apply_local_front_matter(workspace, paper_id):
    patch, profiles, proofs = local_front_matter(workspace.bundle(paper_id))
    if patch:
        workspace.update(paper_id, patch)
        state = workspace.read('paper', paper_id, {})
        state['metadata_source'] = 'first_page_text_coordinates'
        state['front_matter_proofs'] = proofs
        if profiles and not state.get('author_profiles'):
            state['author_profiles'] = profiles
        workspace.put('paper', paper_id, state, 'front_matter_recovered')
    return patch
