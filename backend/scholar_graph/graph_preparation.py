"""Explicitly rebuild operational bibliography sidecars, retaining frozen parse records."""
from .front_matter import apply_local_front_matter
from .normalize import reference_entries,citation_links
from .reference_identity import title_key
from .errors import PipelineError
import hashlib,json

def prepare_graph(workspace,paper_ids):
    if not 1<=len(paper_ids)<=100 or len(set(paper_ids))!=len(paper_ids):raise PipelineError('VALIDATION_ERROR','请选择1–100篇不同论文。')
    for pid in paper_ids:workspace.metadata(pid)
    changes=[]
    for pid in paper_ids:
        state=workspace.read('paper',pid,{})
        bundle=workspace.bundle(pid)
        previous=workspace.read('enrichment',pid,{})
        source_hash=hashlib.sha256(json.dumps(bundle['chunks'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        revision='20261029-bibliography-v5'
        if previous.get('reference_parser')==revision and previous.get('reference_input_sha256')==source_hash:
            changes.append({'paper_id':pid,'metadata_patch':{},'reused_source_bibliography':True});continue
        # No repeated header/profile extraction for an unchanged, prepared source.
        # Explicit user corrections still outrank automatic recovery.
        patch=apply_local_front_matter(workspace,pid) if not state.get('metadata') or state.get('metadata_source')=='first_page_text_coordinates' else {}
        if patch:bundle=workspace.bundle(pid)
        refs=reference_entries(bundle['chunks'],pid) or bundle['reference_entries']
        old_by_number={r['number']:r for r in bundle['reference_entries']}
        for ref in refs:
            old=old_by_number.get(ref['number'])
            if old and title_key(old['title'])==title_key(ref['title']):
                for key in ('doi','arxiv_id'):
                    if not ref[key] and old[key]:ref[key]=old[key]
        links=citation_links(bundle['chunks'],refs)
        stable_ids={r['ref_id'] for r in refs if r['number'] in old_by_number and
            title_key(r['title'])==title_key(old_by_number[r['number']]['title'])}
        links+= [link for link in bundle['citation_links'] if link['ref_id'] in stable_ids]
        links=list({tuple(link[k] for k in ('paper_id','citation_number','page_number','chunk_id','ref_id')):link for link in links}.values())
        revised={**bundle,'reference_entries':refs,'citation_links':links};workspace.repository.gate.bundle(revised)
        workspace.put('enrichment',pid,{**previous,'references':refs,'citation_links':links,'reference_parser':revision,'reference_input_sha256':source_hash},'bibliography_rebuilt_from_original_chunks')
        changes.append({'paper_id':pid,'metadata_patch':patch,'references_before':len(bundle['reference_entries']),'references_after':len(refs),'links_before':len(bundle['citation_links']),'links_after':len(links)})
    return changes
