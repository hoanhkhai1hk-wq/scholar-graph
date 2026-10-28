"""Narrow official-case checks; semantic source review is still required."""
import re
import hashlib
import json


def context_transition_supported(citations, gpt2_id):
    # The later paper explicitly supplies BOTH the previous and new window.
    # Requiring GPT-1 p5 as well rejects a valid attributed joint-source answer.
    return any(c['anchor']['paper_id']==gpt2_id and c['anchor']['page_number']==4
               and 'contextsizefrom512to1024tokens' in re.sub(r'\s+', '', c['quote']).lower()
               for c in citations)


def unsupported_metric_refused(value):
    """Check refusal structure; meaning must be reviewed against the source."""
    paragraphs=value.get('paragraphs',[])
    if value.get('refused') is not True or value.get('calculations') or not paragraphs:
        return False
    if any(p['kind']!='limitation' for p in paragraphs):
        return False
    return True


def result_digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()


def source_review_matches(value,review):
    """A missing, failed or stale review can never approve a different result."""
    return isinstance(review,dict) and review.get('passed') is True and bool(review.get('notes','').strip()) and review.get('result_sha256')==result_digest(value)
