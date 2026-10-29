"""Recover fenced code from PDF text geometry without reordering prose columns.

Only a complete, character-for-character matching source region is accepted.
Chunk identities and bounding boxes survive; old publication files stay frozen.
"""
import re
from collections import defaultdict

VERSION = 'pdf-fenced-code-v1'
FENCE = re.compile(r'(?m)^[ \t]*(`{3,}|~{3,})([^\n]*)\n')


def compact(text):
    return re.sub(r'\s+', '', text)


def fenced_regions(text):
    position = 0
    while match := FENCE.search(text, position):
        marker, info = match[1], match[2].strip()
        closing = re.search(r'(?m)^[ \t]*' + re.escape(marker[0]) + '{' + str(len(marker)) + r',}[ \t]*$', text[match.end():])
        if closing is None:
            break
        end = match.end() + closing.end()
        raw = text[match.start():end]
        margin = len(raw) - len(raw.lstrip(' \t'))
        lines = raw.split('\n')
        # Layout extraction has already reconstructed spaces from PDF geometry.
        code = '\n'.join(line[margin:] if not line.strip() or line.startswith(' ' * margin) else line for line in lines)
        yield marker, info, code
        position = end


def repair_page(chunks, text):
    """Return only verified replacements; never globally sort a PDF page."""
    result, changes = list(chunks), []
    for marker, info, code in fenced_regions(text):
        opening = marker + info
        starters = [c for c in result if opening in c['text'] and c.get('bbox')]
        for start in starters:
            offset = start['text'].find(opening)
            prefix = start['text'][:offset].rstrip()
            # Complete code may already live in one chunk.
            if compact(start['text'][offset:]) == compact(code):
                cohort = [start]
            else:
                endings = [c for c in result if c.get('bbox') and c['chunk_id'] != start['chunk_id']
                           and c['text'].strip() == marker and c['bbox'][1] > start['bbox'][1]
                           and abs(c['bbox'][0] - start['bbox'][0]) < .02]
                if len(endings) != 1:
                    continue
                end = endings[0]
                cohort = [c for c in result if c.get('bbox') and c.get('type') == 'text'
                          and start['bbox'][1] <= c['bbox'][1] <= end['bbox'][1]
                          and c['bbox'][0] >= start['bbox'][0] - .005]
                cohort.sort(key=lambda c: (c['bbox'][1], c['bbox'][0]))
            if not cohort or cohort[0]['chunk_id'] != start['chunk_id']:
                continue
            pieces = [c['text'][offset:] if n == 0 else c['text'] for n, c in enumerate(cohort)]
            if compact(''.join(pieces)) != compact(code):
                continue
            # Partition the exact source region over existing IDs, retaining
            # every newline and indentation, including at chunk boundaries.
            positions = [i for i, char in enumerate(code) if not char.isspace()]
            consumed, begin, replacements = 0, 0, []
            for n, (chunk, piece) in enumerate(zip(cohort, pieces)):
                consumed += len(compact(piece))
                stop = len(code) if n == len(cohort) - 1 else positions[consumed - 1] + 1
                restored = code[begin:stop]
                if n == 0 and prefix:
                    restored = prefix + '\n' + restored
                replacements.append({**chunk, 'text': restored})
                begin = stop
            ids = {c['chunk_id'] for c in cohort}
            first = min(i for i, c in enumerate(result) if c['chunk_id'] in ids)
            result = [c for c in result if c['chunk_id'] not in ids]
            result[first:first] = replacements
            changes.append({'chunk_ids': [c['chunk_id'] for c in replacements], 'source': 'pypdf_layout_exact_characters'})
            break
    return result, changes


def repair_pdf_code(chunks, path):
    by_page = defaultdict(list)
    for chunk in chunks:
        by_page[chunk['page_number']].append(chunk)
    pages = [number for number, group in by_page.items() if any('```' in c['text'] or '~~~' in c['text'] for c in group)]
    if not pages:
        return chunks, []
    from pypdf import PdfReader
    changes = []
    with open(path, 'rb') as stream:
        reader = PdfReader(stream)
        for number in pages:
            group, corrected = repair_page(by_page[number], reader.pages[number - 1].extract_text(extraction_mode='layout'))
            by_page[number] = group
            changes.extend({'page_number': number, **change} for change in corrected)
    return [chunk for number in sorted(by_page) for chunk in by_page[number]], changes


def code_ranges(chunks):
    """Protected spans across chunk/batch boundaries, including comments."""
    spans, active = {}, None
    for chunk in chunks:
        text = chunk['text']
        position = 0
        begin = 0 if active else None
        for line in text.splitlines(keepends=True):
            match = re.match(r'^[ \t]*(`{3,}|~{3,})([^\r\n]*)', line)
            if match:
                if active is None:
                    active = match[1]
                    begin = position
                elif match[1][0] == active[0] and len(match[1]) >= len(active) and not match[2].strip():
                    spans[chunk['chunk_id']] = (begin, position + len(line))
                    active, begin = None, None
            position += len(line)
        if begin is not None:
            spans[chunk['chunk_id']] = (begin, len(text))
    return spans


def join_code(parts):
    result = ''
    for part in parts:
        result += ('\n' if result and not result.endswith('\n') and not part.startswith('\n') else '') + part
    return result
