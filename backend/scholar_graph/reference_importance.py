"""Explainable citation-context triage; never infer authors' citation intent."""
import math
import re
from html import unescape

from .qa_evidence import terms
from .validation import chunk_anchor

METHOD = re.compile(r'architecture|training|optimizer|regularization|embedding|encoder|decoder', re.I)
BACKGROUND = re.compile(r'introduction|background|related work', re.I)
ADOPTION = re.compile(r'\bwe (?:use[ds]?|employ|train(?:ed)?|follow|adopt|share)|followed by|weight (?:matrix|matrices)|residual connection|layer normalization|dropout|byte.pair|word.piece', re.I)
MARKER = re.compile(r'\[\s*(\d+(?:\s*[,–-]\s*\d+)*)\s*\]')
FORMULA = 'content_score=4*method+3*adoption+2*title_overlap+log2(1+distinct_citation_chunks)+0.5*comparison-1*background_only; flags from anchored citation context; not a probability'


def numbers(value):
    result = set()
    for part in value.split(','):
        ends = re.split(r'[–-]', part.strip())
        if len(ends) == 1:
            result.add(int(ends[0]))
        elif len(ends) == 2 and 0 < int(ends[1])-int(ends[0]) <= 100:
            result.update(range(int(ends[0]), int(ends[1])+1))
    return result


def citation_context(chunk, number):
    plain = unescape(re.sub(r'<[^>]+>', ' ', chunk['text']))
    sentences = re.split(r'(?<=[.!?])\s+', plain)
    selected = [s for s in sentences if any(number in numbers(m[1]) for m in MARKER.finditer(s))]
    # A parsed link whose marker text is incomplete stays visible, with uncertainty.
    return ' '.join(selected) or plain[:700], bool(selected)


def rank_references(bundle):
    by_id = {c['chunk_id']: c for c in bundle['chunks']}
    result = []
    for ref in bundle['reference_entries']:
        ids = list(dict.fromkeys(l['chunk_id'] for l in bundle['citation_links'] if l['ref_id'] == ref['ref_id']))
        contexts, method, adoption, background, comparison = [], False, False, False, False
        overlap = set()
        for cid in ids:
            chunk = by_id[cid]
            quote, marker_verified = citation_context(chunk, ref['number'])
            path = ' / '.join(chunk['section_path'])
            table = chunk['type'] == 'table'
            method |= bool(METHOD.search(path)) and not table
            adoption |= bool(ADOPTION.search(quote)) and not table and not BACKGROUND.search(path)
            background |= bool(BACKGROUND.search(path))
            comparison |= table or bool(re.search(r'result|comparison|self.attention',path,re.I))
            overlap |= terms(ref['title'] or '') & terms(quote)
            contexts.append({'quote':quote[:700], 'anchor':chunk_anchor(chunk), 'marker_verified':marker_verified})
        # Title/context overlap is capped; a long title cannot swamp an actual method citation.
        lexical = min(len(overlap)/4, 1)
        score = 4*method+3*adoption+2*lexical+math.log2(1+len(ids))+.5*comparison-(background and not method and not comparison)
        if not ids:
            score = 0
        reasons = []
        if method: reasons.append('在方法或训练章节有正文引用')
        if adoption: reasons.append('引用所在语句包含方法采用或实现用语，需结合原文核对')
        if comparison: reasons.append('出现在方法或实验对比中')
        if background and not method and not comparison: reasons.append('目前只发现背景章节引用，降低优先级')
        if not ids: reasons.append('未解析到正文引用，重要性暂不确定')
        result.append({'reference':ref,'importance':len(ids),'citation_chunks':ids,
            'basis':f'本篇内 {len(ids)} 个不同正文段落引用；不是全网引用数。',
            'acquisition_ready':bool(ref['title'] or ref['arxiv_id'] or ref['doi']),
            'content_score':round(score,6),'content_reasons':reasons,'content_contexts':contexts,
            'content_flags':{'method':method,'adoption':adoption,'comparison':comparison,'background':background,'title_overlap':lexical},
            'content_formula':FORMULA,
            'screening_limit':'可解释的上下文启发式排序，不判断引用动机，不自动删除文献。'})
    return sorted(result,key=lambda row:(-row['content_score'],-row['importance'],row['reference']['number']))
