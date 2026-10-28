"""Map authors to first-page contact blocks; never fan out a global affiliation.

GROBID can attach one affiliation to every author in multi-column headers. Only
an institution literally between a matched name and its own email is adopted.
Other fields remain missing with their source retained for manual correction.
"""
import re
from .validation import chunk_anchor

ORG = re.compile(r'\b(?:google|openai|microsoft|anthropic|facebook|meta|university|research|institute|department|laboratory|laboratories|college|school)\b', re.I)
EMAIL = re.compile(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}')


def normalize(value):
    return ''.join(c for c in value.casefold() if c.isalnum())


def expanded_header_names(bundle, names):
    chunks = [c for c in bundle['chunks'] if c['page_number'] == 1 and c.get('bbox') and c['type'] == 'text']
    known = [c for c in chunks if any(normalize(n) in normalize(c['text']) for n in names)]
    abstracts = [c['bbox'][1] for c in chunks if c['text'].strip().casefold() == 'abstract']
    if (not known and names) or not abstracts:
        return names
    minimum = min(c['bbox'][1] for c in known) - .01 if known else 0
    maximum = min(abstracts)
    candidates = []
    for chunk in chunks:
        text = re.sub(r'(?:\s*[∗*†‡\d])+\s*$', '', chunk['text'].strip()).strip()
        if (not minimum <= chunk['bbox'][1] < maximum or ORG.search(text) or EMAIL.search(text)
                or not 2 <= len(text.split()) <= 5 or len(text) > 80
                or normalize(text) == normalize(bundle['paper_meta']['title'] or '')
                or not re.fullmatch(r"[^\W\d_](?:[^\W\d_]|[.'’\-])*(?:\s+[^\W\d_](?:[^\W\d_]|[.'’\-])*){1,4}", text)
                or not all(word[:1].isupper() or word in ('van', 'von', 'de', 'del', 'der', 'da', 'di') for word in text.split())):
            continue
        row = round((chunk['bbox'][1] + chunk['bbox'][3]) / .04)
        candidates.append((row, chunk['bbox'][0], text))
    rows = {row for row, _, _ in candidates if sum(c[0] == row for c in candidates) >= 2}
    if not names and len(candidates) >= 3 and rows:
        return [c[2] for c in sorted(candidates)]
    candidates = [c for c in candidates if c[0] in rows]
    # Recover omitted rows only from an actual multi-column person-name grid.
    if len(candidates) >= len(names) + 3 and all(any(normalize(n) == normalize(c[2]) for c in candidates) for n in names):
        return [c[2] for c in sorted(candidates)]
    return names


def source_author_profiles(bundle, names):
    names = expanded_header_names(bundle, [name for name in names if not ORG.search(name)])
    chunks = [c for c in bundle['chunks'] if c['page_number'] == 1 and c['type'] == 'text']
    profiles = []
    abstract_y = min((c['bbox'][1] for c in chunks if c.get('bbox') and c['text'].strip().casefold() == 'abstract'), default=0)
    # A grouped contact such as {jacobdevlin,...}@google.com contains the
    # normalized author name too; it is not another author-name row.
    author_bottom = max((c['bbox'][3] for c in chunks if c.get('bbox') and '@' not in c['text']
                         and c['bbox'][1] < abstract_y and not ORG.search(c['text'])
                         and any(normalize(name) in normalize(c['text']) for name in names)), default=1)
    shared = [c for c in chunks if c.get('bbox') and author_bottom <= c['bbox'][1] < abstract_y
              and ORG.search(c['text']) and '@' not in c['text'] and len(c['text']) < 100
              and not re.search(r'work performed|contribution|conference|copyright', c['text'], re.I)
              and not any(other.get('bbox') and EMAIL.fullmatch(other['text'].strip())
                          and 0 <= other['bbox'][1]-c['bbox'][3] < .025
                          and abs((other['bbox'][0]+other['bbox'][2]-c['bbox'][0]-c['bbox'][2])/2) < .06
                          for other in chunks)]
    for name in names:
        key = normalize(name)
        match = None
        for chunk in chunks:
            text = chunk['text']
            mapping = [i for i, c in enumerate(text) if c.isalnum()]
            normalized = normalize(text)
            at = normalized.find(key)
            if at < 0 or not key or at + len(key) > len(mapping):
                continue
            # Headers must precede Abstract, never match a later contribution note.
            if chunk.get('bbox') and chunk['bbox'][1] > .6:
                continue
            match = (chunk, mapping[at], mapping[at + len(key) - 1] + 1)
            break
        institutions, emails, evidence = [], [], []
        center = (999, 999)
        actual_name = name
        if match:
            chunk, start, stop = match
            actual_name = chunk['text'][start:stop]
            text = chunk['text']
            other_positions = []
            for other in names:
                needle = normalize(other)
                offset = normalize(text).find(needle)
                if offset >= 0:
                    mapping = [i for i, c in enumerate(text) if c.isalnum()]
                    other_positions.append(mapping[offset])
            next_name = min((p for p in other_positions if p > start), default=len(text))
            contact = text[stop:next_name]
            email = EMAIL.search(contact)
            if email:
                emails = [email[0]]
                affiliation = re.sub(r'^[\s∗*†‡,;]+', '', contact[:email.start()]).strip()
                if affiliation and ORG.search(affiliation) and len(affiliation) <= 200:
                    institutions = [affiliation]
            bbox = chunk.get('bbox')
            if bbox:
                row = sorted(set(other_positions)).index(start)
                center = (round((bbox[1] + (row + .5) * (bbox[3] - bbox[1]) / max(1, len(other_positions))) / .02), bbox[0])
                if not emails:
                    # A separate email block must be directly below the same column.
                    adjacent = [c for c in chunks if EMAIL.fullmatch(c['text'].strip()) and c.get('bbox')
                        and 0 <= c['bbox'][1] - bbox[3] < .035
                        and abs((c['bbox'][0] + c['bbox'][2] - bbox[0] - bbox[2]) / 2) < .06]
                    if len(adjacent) == 1:
                        emails = [adjacent[0]['text'].strip()]
                        evidence.append(chunk_anchor(adjacent[0]))
                        orgs = [c for c in chunks if c.get('bbox') and ORG.search(c['text']) and not EMAIL.search(c['text'])
                                and len(c['text']) <= 200 and bbox[3]-.002 <= c['bbox'][1] <= adjacent[0]['bbox'][1]
                                and c['bbox'][3] <= adjacent[0]['bbox'][1]+.008
                                and abs((c['bbox'][0]+c['bbox'][2]-bbox[0]-bbox[2])/2) < .06]
                        if len(orgs) == 1:
                            institutions = [orgs[0]['text'].strip()]
                            evidence.append(chunk_anchor(orgs[0]))
            evidence.append(chunk_anchor(chunk))
            if not institutions and len(shared) == 1:
                institutions = [shared[0]['text'].strip()]
                evidence.append(chunk_anchor(shared[0]))
            markers = set(re.findall(r'[∗*†‡]', contact))
            for marker in markers:
                for footnote in chunks:
                    if not abstract_y or not footnote.get('bbox') or footnote['bbox'][1] < abstract_y or EMAIL.search(footnote['text']):
                        continue
                    found = re.search(re.escape(marker) + r'\s*([^∗*†‡]{1,200})$', footnote['text'])
                    if not found or re.search(r'work performed|contribution|conference|copyright', found[1], re.I):
                        continue
                    affiliations = [part.strip(' .') for part in found[1].split(',') if ORG.search(part)]
                    if affiliations:
                        institutions = list(dict.fromkeys(institutions + affiliations))
                        evidence.append(chunk_anchor(footnote))
        profiles.append({'name': actual_name, 'institutions': institutions, 'emails': emails,
                         'anchors': evidence, 'source': 'matched_first_page_contact_block' if evidence else 'header_name_only',
                         'missing_fields': [key for key, value in [('institution', institutions), ('email', emails)] if not value],
                         'review_status': 'source_matched_semantic_review_required', '_position': center})
    if profiles and all(p['_position'][0] != 999 for p in profiles):
        profiles.sort(key=lambda p: p['_position'])
    for index, profile in enumerate(profiles, 1):
        profile.pop('_position')
        profile['order'] = index
    return profiles
