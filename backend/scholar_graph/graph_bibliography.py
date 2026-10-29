"""Recover v2 paper-level citations from unique full titles in original bibliography.

No body occurrence or numbered reference is invented. The evidence is explicitly
the actual bibliography passage, with its own original chunk/page anchors.
"""
import unicodedata
import re
from .normalize import is_references
from .reference_identity import title_key,YEAR
from .validation import chunk_anchor

def title_witnesses(bundle,profiles,gate,bundles):
    chunks=[c for c in bundle['chunks'] if is_references(c)]
    text='';spans=[]
    for chunk in chunks:
        local='';offsets=[]
        for i,ch in enumerate(chunk['text']):
            for letter in unicodedata.normalize('NFKC',ch).casefold():
                if letter.isalnum():local+=letter;offsets.append(i)
        spans.append((len(text),len(text)+len(local),chunk,offsets));text+=local
    grouped={}
    for profile in profiles:
        for title in profile['titles']:
            key=title_key(title['text'])
            if len(key)>=20:grouped.setdefault(key,set()).add(profile['paper']['id'])
    for title,targets in grouped.items():
        if len(targets)!=1:continue
        target=next(iter(targets))
        if target==bundle['paper_meta']['id']:continue
        at=text.find(title)
        if at<0:continue
        quotes=[];source_year=None;author_context=False
        for start,stop,chunk,offsets in spans:
            if stop<=at or start>=at+len(title):continue
            a=offsets[max(0,at-start)];z=offsets[min(len(offsets)-1,at+len(title)-start-1)]+1
            prefix=chunk['text'][max(0,a-180):a]
            author_context=author_context or bool(re.search(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b|\b[A-Z]\.\s*[A-Z][a-z]+|\b[A-Za-z]+-AI\.',prefix))
            if at+len(title)<=stop:
                year=YEAR.search(chunk['text'][z:z+500]);source_year=int(year[1]) if year else None
            a=max(0,a-80);quote=chunk['text'][a:max(z,min(len(chunk['text']),a+600))][:600]
            gate.anchor(chunk_anchor(chunk),bundles,quote=quote)
            quotes.append({'anchor':chunk_anchor(chunk),'quote':quote})
        if quotes and (source_year is not None or author_context):yield target,title,quotes,source_year
