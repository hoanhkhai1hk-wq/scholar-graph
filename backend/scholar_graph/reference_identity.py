"""Deterministic bibliography extraction and auditable local identity resolution."""

import re
import unicodedata

ARXIV = re.compile(r'(?:arxiv\s*:\s*|arxiv\.org/(?:abs|pdf)/|\babs/)'
                   r'((?:\d{4}\.\d{4,5}|[a-z][a-z.\-]+/\d{7})(?:v\d+)?)', re.I)
DOI = re.compile(r'10\.\d{4,9}/[^\s<>"\]]+', re.I)
YEAR = re.compile(r'(?<![\w/:.])((?:18|19|20)\d{2})(?!\d|\.\d)')


def doi(value):
    match = DOI.search(value or '')
    if not match:
        return None
    result = match[0].rstrip('.,;:')
    while result.endswith(')') and result.count(')') > result.count('('):
        result = result[:-1]
    return result.casefold() or None


def arxiv(value):
    match = ARXIV.search(value or '')
    return match[1].removesuffix('.pdf').casefold() if match else None


def arxiv_key(value):
    value = arxiv(value) or (value or '').strip().casefold()
    return re.sub(r'v\d+$', '', value)


def title_key(value):
    return ''.join(c for c in unicodedata.normalize('NFKC', value or '').casefold() if c.isalnum())


def split_sentence(value, *, author_prefix=False):
    # A period after a one-letter initial is not the author/title boundary.
    for match in re.finditer(r'\.\s+', value):
        last = value[:match.start()].split()[-1:]
        initial=bool(last and re.fullmatch(r'(?:[A-Za-zÀ-ž]\.-?)*[A-Za-zÀ-ž]',last[0].strip('.')))
        if last and (not author_prefix or not initial):
            return value[:match.start()].strip(), value[match.end():].strip()
    return value.strip().rstrip('.'), ''


def author_list(value):
    return [part.strip(' ,;') for part in re.split(r',\s*(?:and\s+)?|\s+and\s+|\s*;\s*', value)
            if part.strip(' ,;')]


def parse_reference(raw):
    raw = re.sub(r'\s+', ' ', raw).strip()
    initials = re.match(r"^((?:(?:[A-ZÀ-ž][\w’'\-]+(?:\s+[a-z][\w\-]+)*,\s*(?:[A-Za-zÀ-ž]\.(?:-?[A-Za-zÀ-ž]\.)*\s*)+)(?:,\s*(?:and\s+)?|\s+and\s+)?)+)\s*(.+)$",raw)
    structured = re.match(r'^(.+?)\s*\(((?:18|19|20)\d{2})\)\.\s*(.+?)\.\s*(.*)$', raw)
    year_first = re.match(r'^(.+?)\.\s+((?:18|19|20)\d{2})[a-z]?\.\s+(.+)$', raw)
    if structured:
        people, date, title, venue = structured.groups()
        names = [people.strip()]
    elif initials:
        people,rest=initials.groups();title,venue=split_sentence(rest)
        years=YEAR.findall(ARXIV.sub('',raw));date=years[-1] if years else None
        names=[p.strip(' ,') for p in re.split(r',\s*(?=[A-ZÀ-ž][a-z])|\s+and\s+',people) if p.strip(' ,')]
    elif year_first:
        people, date, rest = year_first.groups()
        title, venue = split_sentence(rest)
        names = author_list(people)
    else:
        people, rest = split_sentence(raw, author_prefix=True)
        title, venue = split_sentence(rest)
        years = YEAR.findall(ARXIV.sub('', raw))
        date = years[-1] if years else None
        names = author_list(people) if rest else []
    identifier=ARXIV.search(title)
    if identifier and identifier.start()>10:title=title[:identifier.start()].rstrip(' ,')
    title=re.sub(r',?\s*(?:18|19|20)\d{2}[a-z]?\s*$','',title).strip(' ,')
    venue = re.split(r'\s*(?:doi:|https?://doi\.org/)', venue, flags=re.I)[0].strip(' .')
    return {'authors': names, 'year': int(date) if date else None, 'title': title or None,
            'venue': venue or None, 'doi': doi(raw), 'arxiv_id': arxiv(raw)}


def bibliography_sources(chunks):
    # Preserve actual chunk boundaries for evidence; page-number-only blocks are
    # ignored. Unnumbered author/year entries receive document-order ordinals.
    from .normalize import is_references
    selected = [c for c in chunks if is_references(c)]
    combined, spans = '', []
    for chunk in selected:
        start = len(combined)
        combined += chunk['text'] + '\n'
        spans.append((start, len(combined) - 1, chunk))
    # An entry begins at a source line/chunk boundary. A table caption after the
    # bibliography can still inherit its section, but its inline "PBMT [15]"
    # must not become a second reference 15 or abort an otherwise valid import.
    symbolic_marker=r'[A-Za-z][A-Za-z0-9+.-]{0,18}\d[A-Za-z0-9+.-]*'
    markers = list(re.finditer(r'(?m)(?:^[ \t]*(?=\[\d+\])|(?=\['+symbolic_marker+r'\]))\[(\d+|'+symbolic_marker+r')\]\s*', combined))
    symbolic = any(not match[1].isdigit() for match in markers)
    result = []
    if markers:
        for index, match in enumerate(markers):
            end = markers[index + 1].start() if index + 1 < len(markers) else len(combined)
            raw = combined[match.end():end].strip()
            number = index + 1 if symbolic else int(match[1])
            if number > 0 and raw:
                result.append({'number': number, 'marker': match[1], 'raw': raw,
                    'chunks': [c for start, stop, c in spans if stop > match.start() and start < end]})
    else:
        for chunk in selected:
            raw = chunk['text'].strip()
            # Require an author prefix and a year sentence; do not turn arbitrary
            # appendix paragraphs or headings into references.
            parsed = parse_reference(raw)
            author_first = bool(re.match(r'^[^\d\W]', raw) and parsed['authors'] and parsed['title']
                and parsed['year'] and len(raw) < 20000 and len(' '.join(parsed['authors'])) < 15000)
            if re.match(r'^[^\d\W].{2,500}?\.\s+(?:18|19|20)\d{2}[a-z]?\.\s+\S', raw) or author_first:
                result.append({'number': len(result) + 1, 'raw': raw, 'chunks': [chunk]})
            elif result and raw[:1].islower() and len(raw.split()) >= 3:
                # A lower-case continuation at a page/column boundary remains
                # part of the preceding entry; its own chunk is retained.
                result[-1]['raw'] += '\n' + raw
                result[-1]['chunks'].append(chunk)
    return result


def surnames(names):
    result = set()
    for name in names:
        for part in author_list(name):
            tokens = part.split()
            if tokens:
                result.add(title_key(tokens[-1]))
    return result - {''}


def author_year_matcher(references, sources=None):
    """Compile a document's unique author/year identities once, preserving order."""
    grouped = {}
    for ref in references:
        if not ref['authors'] or not ref['year']:
            continue
        people = [part for name in ref['authors'] for part in author_list(name)]
        surname = people[0].split()[-1] if people and people[0].split() else ''
        if len(surname) < 2:
            continue
        key = (surname.casefold(), ref['year'])
        grouped.setdefault(key, []).append(ref)
    patterns = []
    for (surname, year), refs in grouped.items():
        if len(refs) != 1:
            # Duplicate bibliography entries for the exact same work do not
            # make the cited paper ambiguous. Distinct works remain ambiguous.
            if (sources and len({r['number'] for r in refs})==len(refs) and refs[0]['title'] and
                len({title_key(r['title']) for r in refs})==1 and
                all(title_key(r['title']) in title_key(sources.get(r['number'],'')) for r in refs) and
                len({arxiv_key(r['arxiv_id']) for r in refs if r['arxiv_id']})<=1 and len({doi(r['doi']) for r in refs if r['doi']})<=1):
                refs=refs[:1]
            else:
                # Different same-author/year works require a literal a/b suffix,
                # read from the bibliography, rather than a guessed body match.
                by_suffix={}
                for ref in refs:
                    labels=set(re.findall(r'(?<!\d)'+str(year)+r'([a-z])(?=[\s.,;:]|$)',(sources or {}).get(ref['number'],'')))
                    if len(labels)==1:
                        by_suffix.setdefault(next(iter(labels)),[]).append(ref)
                for suffix,suffixed in by_suffix.items():
                    if len(suffixed)==1:
                        patterns.append((str(year),re.compile(r'(?<!\w)'+re.escape(surname)+r'(?:\s+et\s+al\.?)?\s*(?:,\s*|\(\s*)'+str(year)+suffix+r'(?!\w)',re.I),suffixed[0]))
                continue
        # Supports Foo et al. (2017), Foo et al., 2017 and Foo and Bar, 2017.
        people = [part for name in refs[0]['authors'] for part in author_list(name)]
        second = (r'|\s+(?:and|&)\s+' + re.escape(people[1].split()[-1])) if len(people) == 2 else ''
        multiple = r'(?:\s+et\s+al\.?' + second + r')?' if len(people) > 1 else ''
        pattern = (r'(?<!\w)' + re.escape(surname) + multiple + r'\s*(?:,\s*|\(\s*)'
                   + str(year) + r'(?![\da-z])')
        patterns.append((str(year), re.compile(pattern, re.I), refs[0]))
    def find(text):
        result = []
        for year, pattern, ref in patterns:
            # An exact literal year is mandatory in the original expression too.
            if year not in text:
                continue
            match = pattern.search(text)
            if match:
                result.append((ref, match[0]))
        return result
    return find


def author_year_markers(text, references):
    """Only unique first-surname/year pairs, explicitly written in body text."""
    return author_year_matcher(references)(text)


def paper_titles(bundle):
    paper = bundle['paper_meta']
    if paper['title']:
        return [{'text': paper['title'], 'anchor': None, 'source': 'PaperMeta.title'}]
    # Legacy local uploads have null PaperMeta.title. Match only a whole short
    # first-page block, before Abstract, never a substring in the body/references.
    from .validation import chunk_anchor
    candidates = []
    for chunk in sorted(bundle['chunks'], key=lambda c: (c['page_number'], c['chunk_id'])):
        if chunk['page_number'] != 1 or chunk['text'].strip().casefold() == 'abstract':
            break
        value = chunk['text'].strip()
        if (chunk['type'] == 'text' and not chunk['section_path'] and 3 <= len(value.split()) <= 35
                and len(value) <= 250 and not re.search(r'@|arxiv:|copyright|permission|\bprovided\b', value, re.I)):
            candidates.append({'text': value, 'anchor': chunk_anchor(chunk), 'source': 'first_page_exact_chunk'})
    return candidates


def resolve_reference(reference, profiles, raw=''):
    extracted = parse_reference(raw) if raw else {}
    identity = {key: reference[key] or extracted.get(key) for key in ('arxiv_id', 'doi', 'title', 'authors', 'year')}
    result = {'target_paper_id': None, 'method': None, 'reason': None, 'attempted_methods': [],
              'identity': identity, 'evidence': []}
    strong = []
    for method, field, key in [('arxiv', 'arxiv_id', arxiv_key), ('doi', 'doi', doi)]:
        if not identity[field]:
            continue
        result['attempted_methods'].append(method)
        matches = [p for p in profiles if p['paper'][field] and key(p['paper'][field]) == key(identity[field])]
        strong.append((method, field, matches))
    if strong:
        nonempty = [{p['paper']['id'] for p in matches} for _, _, matches in strong if matches]
        ids = set.intersection(*nonempty) if nonempty else set()
        if nonempty and not ids:
            result['reason'] = 'conflicting_identity'
            return result
        matches = [p for p in profiles if p['paper']['id'] in ids]
        if len(matches) == 1:
            target = matches[0]
            for method, field, _ in strong:
                current = target['paper'][field]
                key = arxiv_key if method == 'arxiv' else doi
                if current and key(current) != key(identity[field]):
                    result['reason'] = 'conflicting_identity'
                    return result
            method, field, _ = next(row for row in strong if row[2])
            result.update(target_paper_id=target['paper']['id'], method=method)
            result['evidence'].append({'field': field, 'reference_value': identity[field],
                'target_value': target['paper'][field], 'normalized': (arxiv_key if method == 'arxiv' else doi)(identity[field])})
            return result
        if matches:
            result['reason'] = 'ambiguous_identity'
            return result
        # A missing target identifier is unknown, not a contradiction. Exact
        # title matching can still resolve such a legacy upload. Known different
        # identifiers are excluded and never overridden by a title guess.
        profiles = [p for p in profiles if all(not p['paper'][field] or
            (arxiv_key if method == 'arxiv' else doi)(p['paper'][field]) ==
            (arxiv_key if method == 'arxiv' else doi)(identity[field]) for method, field, _ in strong)]
        if not profiles:
            result['reason'] = 'not_in_selection'
            return result
    title = title_key(identity['title'])
    result['attempted_methods'].append('title' if title else 'author-year')
    matches, auxiliary_conflict = [], False
    for profile in profiles:
        paper = profile['paper']
        if title:
            titles = [item for item in profile['titles'] if title_key(item['text']) == title]
            if not titles:
                continue
        else:
            titles = []
        # Years and surnames support exact title matching; incomplete metadata is
        # explicitly unknown. They never rescue a conflicting nonempty title.
        submission_only = profile.get('year_basis') == 'arxiv_submission_identifier'
        same_year = not submission_only and identity['year'] is not None and paper['year'] is not None and identity['year'] == paper['year']
        left, right = surnames(identity['authors'] or []), surnames(paper['authors'])
        overlap = sorted(left & right)
        if title:
            if (not submission_only and identity['year'] and paper['year'] and not same_year) or (left and right and not overlap):
                auxiliary_conflict = True
                continue
        else:
            left_names = [part for name in identity['authors'] or [] for part in author_list(name)]
            right_names = [part for name in paper['authors'] for part in author_list(name)]
            # A surname/year alone is never a sufficient identity. This final
            # fallback requires the complete, non-initialized author-name set.
            full_names = all(len(name.split()) >= 2 and len(name.split()[0].strip('.')) > 1
                             for name in left_names + right_names)
            if not (same_year and left and full_names and
                    {title_key(name) for name in left_names} == {title_key(name) for name in right_names}):
                continue
        matches.append((profile, titles, same_year, overlap))
    if len(matches) == 1:
        profile, titles, same_year, overlap = matches[0]
        result.update(target_paper_id=profile['paper']['id'], method='title' if title else 'author-year')
        result['evidence'].append({'field': 'title' if title else 'authors_year', 'reference_value': identity['title'],
            'target_title': titles[0] if titles else None, 'normalized_title': title or None,
            'year_agrees': same_year, 'reference_year': identity['year'], 'target_year': profile['paper']['year'],
            **({'target_year_basis': profile['year_basis']} if profile.get('year_basis') else {}),
            'shared_surnames': overlap, 'auxiliary_missing': [key for key in ('year', 'authors')
                if not identity[key] or not profile['paper'][key]]})
    else:
        result['reason'] = ('ambiguous_identity' if matches else 'not_in_selection'
                            if title or (identity['authors'] and identity['year']) else 'insufficient_identity')
        if not matches and auxiliary_conflict:
            result['reason'] = 'conflicting_auxiliary'
    return result
