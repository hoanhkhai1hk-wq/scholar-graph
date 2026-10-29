"""Locate real abstract/introduction chunks for narrowly recognized overview questions."""
import re
import unicodedata

from .grounded_model import evidence_from_chunks


def is_overview_question(question):
    text = unicodedata.normalize('NFKC', question).casefold()
    text = re.sub(r'[\s，,。.!！?？:：;；]+', '', text)
    subject = r'(?:这篇|这|该篇|该|本篇|本|此篇|此)?(?:论文|文章|文献|研究)'
    direct = subject + r'(?:主要|大概|大致|总体|究竟)?(?:是)?(?:关于|讲述|讲了|讲的|讲|介绍|研究|讨论|写了|做了|说)(?:的|是|了)?(?:什么|什么内容|啥|哪些内容|什么问题)(?:的|吗|呢)?'
    named = subject + r'(?:的)?(?:主要内容|研究内容|核心内容|内容|主题|主旨)(?:是什么|有哪些|是啥|是什么的)?'
    request = r'(?:请问|请|麻烦|能否|可以|能不能|帮我|给我|简单|简要|大致)*' + r'(?:概括|总结|介绍|解释|说明|说说|讲讲)(?:一下)?' + subject + r'(?:的)?(?:主要内容|研究内容|核心内容|内容|主题|主旨|摘要|概要)?'
    english = r'(?:what(?:is|s)thispaperabout|whatdoesthispaper(?:discuss|study|describe)|summari[sz]e(?:this|the)paper|give(?:me)?anoverviewof(?:this|the)paper)'
    casual = r'(?:请|帮我|简单|简要|能否|可以|一下|这篇|这|该|本|此|它|论文|文章|研究|的)*(?:(?:主要|核心|关键)?(?:创新点|贡献|亮点|研究意义|思想|方法)(?:是什么|有哪些|是啥|在哪|在哪里|有什么)?|(?:主要)?(?:讲了|讲|做了|研究了)(?:啥|什么)(?:内容|问题)?)(?:吗|呢|啊)?'
    return bool(re.fullmatch(direct, text) or re.fullmatch(named, text) or
                re.fullmatch(request, text) or re.fullmatch(english, text) or re.fullmatch(casual,text))


def overview_evidence(workspace, bundle, question, *, limit=24, for_comparison=False):
    """Only publish verbatim passages anchored to this paper, never a generated abstract."""
    if not for_comparison and not is_overview_question(question):
        return []
    paper_id = bundle['paper_meta']['id']
    state = workspace.read('paper', paper_id, {})
    proof_ids = set(state.get('front_matter_proofs', {}).get('abstract', []))
    abstract, introduction = [], []
    for chunk in bundle['chunks']:
        text = chunk['text'].strip()
        if abstract and re.fullmatch(r'(?:1\.?\s*)?(?:introduction|引言|绪论)',text,re.I):
            break
        if chunk['type'] != 'text' or len(text) < 25 or len(re.findall(r'[A-Za-z\u3400-\u9fff]', text)) < 15:
            continue
        if re.match(r'^[*∗†‡]|^(?:arxiv|https?://|copyright)\b', text, re.I):
            continue
        path = chunk['section_path']
        # Some PDFs have stale "Abstract" paths across later numbered headings.
        # Keep the literal abstract boundary rather than dragging the whole paper in.
        if (chunk['page_number'] == 1 and chunk['chunk_id'] in proof_ids) or any(re.fullmatch(r'abstract|摘要', part.strip(), re.I) for part in path):
            if abstract and chunk['page_number']>abstract[0]['page_number']+1:
                continue
            abstract.append(chunk)
        elif any(re.fullmatch(r'(?:\d+(?:\.\d+)*\s*)?(?:introduction|引言|绪论)', part.strip(), re.I) for part in path):
            introduction.append(chunk)
    # Introduction is a fallback for documents with no identified abstract.
    if not abstract and introduction:
        first_page = min(chunk['page_number'] for chunk in introduction)
        introduction = [chunk for chunk in introduction if chunk['page_number'] <= first_page + 1]
    ordered = abstract if abstract else introduction
    return evidence_from_chunks(bundle, ordered, question, limit=limit)
