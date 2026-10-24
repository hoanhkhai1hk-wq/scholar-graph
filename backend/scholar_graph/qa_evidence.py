"""Deterministic lexical retrieval of bounded, contiguous source quotations."""

import math
import re

from .validation import chunk_anchor

FACETS = {
    "samples": ("samples", "sample size", "sample", "样本", "数据规模"),
    "f1": ("f1",), "mrr": ("mrr",), "ndcg": ("ndcg",),
    "future": ("future work", "未来工作", "未来方向"),
    "efficiency": ("efficiency", "推理效率", "inference speed"),
    "prototype": ("prototype calibration", "原型校准"),
    "crosslingual": ("cross-lingual", "cross language", "跨语言"),
    "dataset": ("datasets", "dataset", "数据集"),
}
STOP = set("what which how many does do is are was were the a an this that paper study author authors report reported of in on to for and it its please describe summarize summarise explain problem mitigate address use uses contains contain".split())
STOP.update("did used using evaluate evaluated inference number size score scores value values".split())
ZH_STOP = ("本文", "论文", "作者", "请问", "请", "提出的", "用来", "缓解", "什么问题", "什么", "多少", "哪些", "如何", "是否", "有没有", "报告的", "具体", "包括", "列出的", "分别", "总结", "说明", "描述", "介绍", "方法", "是多少", "是多少", "了", "的", "吗", "是", "在", "和", "与")


def facets(text):
    lower = text.casefold()
    return {key for key, aliases in FACETS.items() if any(alias in lower for alias in aliases)}


def terms(text):
    lower = text.casefold()
    result = set()
    for key, aliases in FACETS.items():
        for alias in aliases:
            if alias in lower:
                result.add("facet:" + key)
                lower = lower.replace(alias, " ")
    result.update(word for word in re.findall(r"[a-z]+(?:-[a-z]+)*", lower) if word not in STOP)
    for phrase in ZH_STOP:
        lower = lower.replace(phrase, " ")
    for run in re.findall(r"[\u4e00-\u9fff]+", lower):
        result.update(run[n:n + 2] for n in range(len(run) - 1))
    return result


def numbers(text):
    # Metric names are identifiers, not reported values (F1, MRR@10, nDCG@10).
    text = re.sub(r"\b(?:f1|(?:mrr|ndcg)(?:@\d+)?)\b", "", text, flags=re.I)
    text = re.sub(r"\[\d+(?:\s*[,–-]\s*\d+)*\]", "", text)
    arabic = re.findall(r"(?<![A-Za-z\d])[-+]?\d+(?:,\d{3})*(?:\.\d+)?(?:[eE][-+]?\d+)?%?", text)
    chinese = re.findall(r"[零一二两三四五六七八九十百千万]+(?=个|条|项|组|倍|种|方向|样本|测试集)", text)
    return {value.replace(",", "") for value in arabic + chinese}


def numeric_question(question):
    return bool(numbers(question) or facets(question) & {"samples", "f1", "mrr", "ndcg"}
                or re.search(r"多少|数值|数字|百分比|how many|how much|percentage|value|score", question, re.I))


def neutral_question(question):
    # Conservative grammar: assertions, why-questions and numerical premises are not endorsed.
    if numbers(question) or re.search(
            r"为什么|为何|既然|因此|所以|替代|不再|只建议|放弃|最差|对吗|证明|忽略|编造|"
            r"不(?:会|能|是|支持|使用|需要|缓解|提升|有效)|没有|未(?:做|能|评估|使用|报告)|"
            r"\b(?:why|given|assum\w*|therefore|prove\w*|abandon\w*|replace\w*|confirm|right|correct|ignore|invent|not|never|without|worst|only)\b",
            question, re.I):
        return False
    return bool(re.search(r"什么|多少|哪些|如何|是否|有没有|总结|说明|描述|介绍|\b(?:what|which|how|describe|summari[sz]e|explain)\b", question, re.I))


def retrieve(bundle, question, limit=8):
    requested = facets(question)
    query = terms(question)
    candidates = []
    for chunk in bundle["chunks"]:
        # Never join across chunks or invent shortened quotations.
        for sentence in re.split(r"(?<=[。！？!?])|(?<=\.)\s+(?=[A-Z])|\n+", chunk["text"]):
            sentence = sentence.strip()
            if not sentence or len(sentence) > 600:
                continue
            tokens = terms(sentence)
            overlap = query & tokens
            if not query or not overlap or not query.issubset(tokens):
                continue
            # Requested metric/topic must occur in the quote, not only in a heading.
            if requested and not requested.issubset(facets(sentence)):
                continue
            score = len(overlap) / math.sqrt(max(len(tokens), 1))
            candidates.append({"anchor": chunk_anchor(chunk), "quote": sentence, "score": score})
    candidates.sort(key=lambda item: (-item["score"], item["anchor"]["page_number"], item["anchor"]["chunk_id"], item["quote"]))
    unique = []
    seen = set()
    for item in candidates:
        key = (item["anchor"]["chunk_id"], item["quote"])
        if key not in seen:
            unique.append(item)
            seen.add(key)
    return unique[:limit]


def measured_samples(text):
    matches = re.findall(r"(\d+(?:,\d{3})*)\s*(?:samples?\b|条样本|个样本)|样本(?:量|数)?(?:为|是|包含|：|:)\s*(\d+(?:,\d{3})*)", text, re.I)
    return {part.replace(",", "") for match in matches for part in match if part}
